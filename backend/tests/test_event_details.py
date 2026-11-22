"""Event details from the manager form: images, full fields, editing (#169)."""
import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from PIL import Image

from routers import manager
from routers.manager import EventCreate
from services import event_images
from services.event_images import EventImageError, process_image

ADMIN = {"id": str(uuid.uuid4()), "roles": ["admin"]}
EVENT_ID = str(uuid.uuid4())


def image_bytes(size=(2400, 3600), fmt="PNG", mode="RGB") -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, (200, 30, 60) if mode == "RGB" else (200, 30, 60, 128)).save(out, format=fmt)
    return out.getvalue()


# ── Image processing ─────────────────────────────────────────────────────────

def test_poster_is_resized_and_saved_as_jpeg():
    jpeg = process_image(image_bytes((2400, 3600)), "poster")
    img = Image.open(io.BytesIO(jpeg))
    assert img.format == "JPEG"
    assert img.size == (1000, 1500)


def test_backdrop_keeps_its_shape_within_1920x1080():
    img = Image.open(io.BytesIO(process_image(image_bytes((3840, 2160), "WEBP"), "backdrop")))
    assert img.size == (1920, 1080)


def test_transparent_png_is_flattened():
    img = Image.open(io.BytesIO(process_image(image_bytes((400, 600), "PNG", "RGBA"), "poster")))
    assert img.mode == "RGB"


@pytest.mark.parametrize(
    "data, kind, message",
    [
        (b"not an image", "poster", "JPG, PNG or WebP"),
        (b"x" * (event_images.MAX_UPLOAD_BYTES + 1), "poster", "5 MB"),
        (image_bytes((10, 10), "GIF"), "poster", "JPG, PNG or WebP"),
        (image_bytes((10, 10)), "banner", "poster or backdrop"),
    ],
)
def test_bad_uploads_are_rejected(data, kind, message):
    with pytest.raises(EventImageError, match=message):
        process_image(data, kind)


class FakeUpload:
    def __init__(self, data: bytes):
        self.data = data

    async def read(self, limit: int = -1) -> bytes:
        return self.data if limit < 0 else self.data[:limit]


@pytest.mark.asyncio
async def test_upload_route_returns_the_public_url(monkeypatch):
    upload = AsyncMock(return_value="https://example.supabase.co/storage/v1/object/public/event-images/u/poster-1.jpg")
    monkeypatch.setattr(manager, "upload_event_image", upload)
    result = await manager.upload_event_image_file(kind="poster", file=FakeUpload(image_bytes((500, 750))), user=ADMIN)
    assert result["url"].endswith("poster-1.jpg")
    user_id, kind, jpeg = upload.await_args.args
    assert (user_id, kind) == (ADMIN["id"], "poster")
    assert Image.open(io.BytesIO(jpeg)).format == "JPEG"


@pytest.mark.asyncio
async def test_upload_route_turns_bad_images_into_400(monkeypatch):
    monkeypatch.setattr(manager, "upload_event_image", AsyncMock())
    with pytest.raises(HTTPException) as err:
        await manager.upload_event_image_file(kind="poster", file=FakeUpload(b"nope"), user=ADMIN)
    assert err.value.status_code == 400
    assert "JPG, PNG or WebP" in err.value.detail


# ── Creating and editing with every field ────────────────────────────────────

def make_conn():
    conn = MagicMock()
    conn.fetchrow = AsyncMock(
        side_effect=lambda sql, *a: {"event_type": "movie", "formats": ["2D"]}
        if sql.startswith("SELECT event_type") else {"id": EVENT_ID}
    )
    conn.fetch = AsyncMock(return_value=[])
    return conn


def update_values(conn) -> dict:
    call = next(c for c in conn.fetchrow.await_args_list if c.args[0].startswith("UPDATE events"))
    sql, args = call.args[0], call.args[2:]
    columns = [part.split("=")[0].strip() for part in sql.split("SET", 1)[1].split(", updated_at")[0].split(",")]
    return dict(zip(columns, args))


@pytest.mark.asyncio
async def test_create_saves_every_detail_from_the_form():
    conn = make_conn()
    body = EventCreate(
        title="Dune: Part Two", event_type="movie", description="Paul joins the Fremen.",
        language="English", genre="Sci-Fi", duration_minutes=166,
        poster_url="https://x/p.jpg", backdrop_url="https://x/b.jpg",
        cast_crew=[{"name": "Timothée Chalamet", "role": "Paul Atreides"}],
        formats=["2D", "IMAX"], certificate="UA", release_date="2024-03-01",
        terms_and_conditions="No outside food.",
    )
    await manager.create_event(body, user=ADMIN, conn=conn)
    args = next(c for c in conn.fetchrow.await_args_list if "INSERT INTO events" in c.args[0]).args
    assert args[1:9] == ("Dune: Part Two", "Paul joins the Fremen.", "movie", 166, "English", "Sci-Fi",
                         "https://x/p.jpg", "https://x/b.jpg")
    assert json.loads(args[11]) == [{"name": "Timothée Chalamet", "role": "Paul Atreides"}]
    assert args[13] == ["2D", "IMAX"]
    assert str(args[15]) == "2024-03-01"
    assert args[16] == "No outside food."


@pytest.mark.asyncio
async def test_editing_saves_cast_artists_and_images(monkeypatch):
    monkeypatch.setattr(manager, "_assert_owns_event", AsyncMock())
    conn = make_conn()
    await manager.update_event(EVENT_ID, {
        "description": "New text",
        "poster_url": "https://x/new.jpg",
        "artists": [{"name": "Band", "role": "Headliner"}],
        "cast_crew": [],
    }, user=ADMIN, conn=conn)
    values = update_values(conn)
    assert values["description"] == "New text"
    assert values["poster_url"] == "https://x/new.jpg"
    assert json.loads(values["artists"]) == [{"name": "Band", "role": "Headliner"}]
    assert json.loads(values["cast_crew"]) == []


@pytest.mark.asyncio
async def test_clearing_the_release_date_stores_null(monkeypatch):
    monkeypatch.setattr(manager, "_assert_owns_event", AsyncMock())
    conn = make_conn()
    await manager.update_event(EVENT_ID, {"release_date": ""}, user=ADMIN, conn=conn)
    assert update_values(conn)["release_date"] is None


@pytest.mark.asyncio
async def test_editing_still_checks_ownership(monkeypatch):
    monkeypatch.setattr(manager, "_assert_owns_event", AsyncMock(side_effect=HTTPException(status_code=403)))
    with pytest.raises(HTTPException) as err:
        await manager.update_event(EVENT_ID, {"title": "x"}, user=ADMIN, conn=make_conn())
    assert err.value.status_code == 403


@pytest.mark.asyncio
async def test_a_concert_gets_no_film_certificate():
    conn = make_conn()
    await manager.create_event(EventCreate(title="Arijit Live", event_type="concert", certificate="UA"), user=ADMIN, conn=conn)
    args = next(c for c in conn.fetchrow.await_args_list if "INSERT INTO events" in c.args[0]).args
    assert args[14] is None


@pytest.mark.asyncio
async def test_a_movie_without_certificate_defaults_to_ua():
    conn = make_conn()
    await manager.create_event(EventCreate(title="Dune", event_type="movie", certificate=""), user=ADMIN, conn=conn)
    args = next(c for c in conn.fetchrow.await_args_list if "INSERT INTO events" in c.args[0]).args
    assert args[14] == "UA"
