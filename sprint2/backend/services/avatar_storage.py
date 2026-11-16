"""
Profile photos (Sprint 2, Tirth).

Photos are stored in a PUBLIC Supabase Storage bucket ("avatars") so they can be
shown anywhere with a plain URL (profile page, reviews).

Every upload is decoded and re-encoded with Pillow:
  - rejects anything that is not a real JPG / PNG / WebP image
  - strips metadata (EXIF, GPS location)
  - resizes to at most 512×512 and saves as JPEG
"""
import io
import uuid
from typing import Optional

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

AVATAR_BUCKET = "avatars"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024          # 2 MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIZE_PX = 512


class AvatarError(Exception):
    """Invalid image or storage failure (message is safe to show to the user)."""


def _headers(content_type: Optional[str] = None) -> dict:
    h = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "apiKey": SUPABASE_SERVICE_KEY}
    if content_type:
        h["Content-Type"] = content_type
    return h


def _base() -> str:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise AvatarError("Photo storage is not configured")
    return SUPABASE_URL.rstrip("/") + "/storage/v1"


def process_image(data: bytes) -> bytes:
    """Validate and normalise an uploaded image. Returns JPEG bytes."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise AvatarError("Photo must be 2 MB or smaller")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.verify()                                   # detects truncated / fake files
        img = Image.open(io.BytesIO(data))             # reopen after verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise AvatarError("Upload a JPG, PNG or WebP image")
    if fmt not in ALLOWED_FORMATS:
        raise AvatarError("Upload a JPG, PNG or WebP image")

    img = ImageOps.exif_transpose(img)                 # keep phone photos upright
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_SIZE_PX, MAX_SIZE_PX))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


async def _ensure_public_bucket(client: httpx.AsyncClient) -> None:
    resp = await client.get(f"{_base()}/bucket/{AVATAR_BUCKET}", headers=_headers())
    if resp.status_code == 200:
        return
    create = await client.post(
        f"{_base()}/bucket",
        headers=_headers("application/json"),
        json={
            "id": AVATAR_BUCKET,
            "name": AVATAR_BUCKET,
            "public": True,
            "file_size_limit": MAX_UPLOAD_BYTES,
            "allowed_mime_types": ["image/jpeg"],
        },
    )
    if create.status_code not in (200, 201) and "already exists" not in create.text.lower():
        raise AvatarError("Could not prepare photo storage")


def public_url(path: str) -> str:
    return f"{_base()}/object/public/{AVATAR_BUCKET}/{path}"


def path_from_url(url: Optional[str]) -> Optional[str]:
    """Return the storage path if the URL points into our avatars bucket."""
    if not url:
        return None
    prefix = f"{_base()}/object/public/{AVATAR_BUCKET}/"
    return url[len(prefix):] if url.startswith(prefix) else None


async def upload_avatar(user_id: str, jpeg_bytes: bytes) -> str:
    """Upload the processed photo and return its public URL."""
    path = f"{user_id}/{uuid.uuid4().hex}.jpg"         # new name each time → no stale browser cache
    async with httpx.AsyncClient(timeout=30.0) as client:
        await _ensure_public_bucket(client)
        resp = await client.post(
            f"{_base()}/object/{AVATAR_BUCKET}/{path}",
            headers=_headers("image/jpeg"),
            content=jpeg_bytes,
        )
        if resp.status_code not in (200, 201):
            raise AvatarError("Could not save the photo, please try again")
    return public_url(path)


async def delete_avatar(url: Optional[str]) -> None:
    """Best-effort delete of an old photo (ignores photos stored elsewhere)."""
    path = path_from_url(url)
    if not path:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.request(
                "DELETE",
                f"{_base()}/object/{AVATAR_BUCKET}",
                headers=_headers("application/json"),
                json={"prefixes": [path]},
            )
    except httpx.HTTPError:
        pass
