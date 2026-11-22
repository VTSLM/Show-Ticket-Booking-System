"""
Event posters and backdrops (#169).

Images are stored in a PUBLIC Supabase Storage bucket ("event-images") so Browse and the
event page can show them with a plain URL.

Every upload is decoded and re-encoded with Pillow, like profile photos:
  - rejects anything that is not a real JPG / PNG / WebP image
  - strips metadata (EXIF, GPS location)
  - resizes to fit the kind (poster 1000×1500, backdrop 1920×1080) and saves as JPEG
"""
import io
import uuid

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

EVENT_IMAGE_BUCKET = "event-images"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024          # 5 MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SIZE_PX = {"poster": (1000, 1500), "backdrop": (1920, 1080)}


class EventImageError(Exception):
    """Invalid image or storage failure (message is safe to show to the user)."""


def _headers(content_type: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "apiKey": SUPABASE_SERVICE_KEY}
    if content_type:
        h["Content-Type"] = content_type
    return h


def _base() -> str:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise EventImageError("Image storage is not configured")
    return SUPABASE_URL.rstrip("/") + "/storage/v1"


def process_image(data: bytes, kind: str) -> bytes:
    """Validate and normalise an uploaded poster or backdrop. Returns JPEG bytes."""
    if kind not in MAX_SIZE_PX:
        raise EventImageError("Image kind must be poster or backdrop")
    if len(data) > MAX_UPLOAD_BYTES:
        raise EventImageError("Image must be 5 MB or smaller")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.verify()                                   # detects truncated / fake files
        img = Image.open(io.BytesIO(data))             # reopen after verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise EventImageError("Upload a JPG, PNG or WebP image")
    if fmt not in ALLOWED_FORMATS:
        raise EventImageError("Upload a JPG, PNG or WebP image")

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (0, 0, 0))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail(MAX_SIZE_PX[kind])

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


async def _ensure_public_bucket(client: httpx.AsyncClient) -> None:
    resp = await client.get(f"{_base()}/bucket/{EVENT_IMAGE_BUCKET}", headers=_headers())
    if resp.status_code == 200:
        return
    create = await client.post(
        f"{_base()}/bucket",
        headers=_headers("application/json"),
        json={
            "id": EVENT_IMAGE_BUCKET,
            "name": EVENT_IMAGE_BUCKET,
            "public": True,
            "file_size_limit": MAX_UPLOAD_BYTES,
            "allowed_mime_types": ["image/jpeg"],
        },
    )
    if create.status_code not in (200, 201) and "already exists" not in create.text.lower():
        raise EventImageError("Could not prepare image storage")


async def upload_event_image(user_id: str, kind: str, jpeg_bytes: bytes) -> str:
    """Upload a processed image and return its public URL."""
    path = f"{user_id}/{kind}-{uuid.uuid4().hex}.jpg"
    async with httpx.AsyncClient(timeout=30.0) as client:
        await _ensure_public_bucket(client)
        resp = await client.post(
            f"{_base()}/object/{EVENT_IMAGE_BUCKET}/{path}",
            headers=_headers("image/jpeg"),
            content=jpeg_bytes,
        )
        if resp.status_code not in (200, 201):
            raise EventImageError("Could not save the image, please try again")
    return f"{_base()}/object/public/{EVENT_IMAGE_BUCKET}/{path}"
