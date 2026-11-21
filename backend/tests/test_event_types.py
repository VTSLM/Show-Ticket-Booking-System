"""#168: cinema formats belong to movies, and the seat map draws a screen only for movies."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from routers import manager
from routers.manager import EventCreate, event_formats
from routers.seats import display_layout

ADMIN = {"id": str(uuid.uuid4()), "roles": ["admin"]}
EVENT_ID = str(uuid.uuid4())


# ── Formats ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("event_type", ["concert", "theatre", "other", "CONCERT"])
def test_non_movie_events_have_no_formats(event_type):
    assert event_formats(event_type, ["2D", "IMAX 3D"]) == []
    assert event_formats(event_type, None) == []


def test_movies_keep_their_formats_without_duplicates():
    assert event_formats("movie", ["2D", " IMAX 3D ", "2D", ""]) == ["2D", "IMAX 3D"]


def test_movies_default_to_2d():
    assert event_formats("movie", None) == ["2D"]
    assert event_formats("movie", []) == ["2D"]
    assert event_formats(None, None) == ["2D"]


def make_conn(current=None):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=lambda sql, *a: current if sql.startswith("SELECT event_type") else {"id": EVENT_ID})
    conn.fetch = AsyncMock(return_value=[])
    return conn


def insert_args(conn):
    call = next(c for c in conn.fetchrow.await_args_list if "INSERT INTO events" in c.args[0])
    return call.args


@pytest.mark.asyncio
async def test_creating_a_concert_stores_no_formats():
    conn = make_conn()
    await manager.create_event(EventCreate(title="Arijit Live", event_type="concert"), user=ADMIN, conn=conn)
    assert insert_args(conn)[13] == []


@pytest.mark.asyncio
async def test_creating_a_movie_stores_2d_by_default():
    conn = make_conn()
    await manager.create_event(EventCreate(title="Dune", event_type="movie"), user=ADMIN, conn=conn)
    assert insert_args(conn)[13] == ["2D"]


def update_values(conn):
    call = next(c for c in conn.fetchrow.await_args_list if c.args[0].startswith("UPDATE events"))
    sql, args = call.args[0], call.args[2:]
    columns = [part.split("=")[0].strip() for part in sql.split("SET", 1)[1].split(", updated_at")[0].split(",")]
    return dict(zip(columns, args))


@pytest.mark.asyncio
async def test_changing_a_movie_to_a_concert_clears_its_formats(monkeypatch):
    monkeypatch.setattr(manager, "_assert_owns_event", AsyncMock())
    conn = make_conn(current={"event_type": "movie", "formats": ["2D", "3D"]})
    await manager.update_event(EVENT_ID, {"event_type": "concert"}, user=ADMIN, conn=conn)
    assert update_values(conn)["formats"] == []


@pytest.mark.asyncio
async def test_formats_sent_for_a_theatre_event_are_ignored(monkeypatch):
    monkeypatch.setattr(manager, "_assert_owns_event", AsyncMock())
    conn = make_conn(current={"event_type": "theatre", "formats": []})
    await manager.update_event(EVENT_ID, {"formats": ["IMAX 3D"]}, user=ADMIN, conn=conn)
    assert update_values(conn)["formats"] == []


@pytest.mark.asyncio
async def test_updating_other_fields_leaves_formats_alone(monkeypatch):
    monkeypatch.setattr(manager, "_assert_owns_event", AsyncMock())
    conn = make_conn(current={"event_type": "movie", "formats": ["3D"]})
    await manager.update_event(EVENT_ID, {"title": "New title"}, user=ADMIN, conn=conn)
    assert "formats" not in update_values(conn)


# ── Seat map arrangement ────────────────────────────────────────────────────

@pytest.mark.parametrize("event_type,venue_layout,expected", [
    ("movie", "cinema", "cinema"),
    ("movie", "concert", "cinema"),       # a movie always gets a screen
    ("movie", None, "cinema"),
    ("concert", "concert", "concert"),
    ("concert", "cinema", "concert"),     # live events never get a cinema screen
    ("concert", "other", "concert"),
    ("theatre", "cinema", "theatre"),
    ("theatre", "theatre", "theatre"),
    ("other", "cinema", "stage"),         # comedy and other events: a plain stage
    ("other", "other", "stage"),
    ("other", "theatre", "theatre"),      # a venue's own stage is kept
    ("concert", "theatre", "theatre"),
])
def test_display_layout(event_type, venue_layout, expected):
    assert display_layout(event_type, venue_layout) == expected


@pytest.mark.parametrize("event_type", ["concert", "theatre", "other"])
@pytest.mark.parametrize("venue_layout", ["cinema", "concert", "theatre", "other", None])
def test_live_events_never_get_a_screen(event_type, venue_layout):
    assert display_layout(event_type, venue_layout) != "cinema"
