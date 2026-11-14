from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
import asyncpg
from database import get_conn
from dependencies import require_role

router = APIRouter(prefix="/api/manager", tags=["manager"])


def _parse_uuid(value: str, field_name: str) -> str:
    try:
        return str(uuid.UUID(str(value).strip()))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_label(index: int) -> str:
    if index < 26:
        return chr(65 + index)
    return f"{chr(65 + (index // 26) - 1)}{chr(65 + (index % 26))}"


async def _generate_seats_for_screen(
    conn: asyncpg.Connection,
    screen_id: str,
    rows: int,
    cols: int,
    max_seats: Optional[int] = None,
) -> None:
    records = []
    for r in range(rows):
        label = _row_label(r)
        for num in range(1, cols + 1):
            if max_seats is not None and len(records) >= max_seats:
                break
            records.append((screen_id, label, num))
        if max_seats is not None and len(records) >= max_seats:
            break
    if records:
        await conn.executemany(
            "INSERT INTO seats (screen_id, row_label, seat_number) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
            records,
        )


# ---- Venues ----
class VenueCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: str
    state: Optional[str] = None
    pincode: Optional[str] = None

    @field_validator("name", "city")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned


@router.get("/venues")
async def list_venues(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch("SELECT * FROM venues ORDER BY name")
    return [dict(r) for r in rows]


@router.post("/venues")
async def create_venue(
    body: VenueCreate,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        "INSERT INTO venues (name, address, city, state, pincode) VALUES ($1,$2,$3,$4,$5) RETURNING *",
        body.name, body.address, body.city, body.state, body.pincode
    )
    return dict(row)


# ---- Screens ----
class ScreenCreate(BaseModel):
    name: str
    capacity: int
    rows: Optional[int] = None
    cols: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Screen name cannot be empty")
        return cleaned

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Screen capacity must be greater than 0")
        return v

    @field_validator("rows", "cols")
    @classmethod
    def validate_dimensions(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Rows and columns must be greater than 0")
        return v


@router.get("/venues/{venue_id}/screens")
async def list_screens(venue_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    parsed_venue_id = _parse_uuid(venue_id, "venue_id")
    rows = await conn.fetch("SELECT * FROM screens WHERE venue_id=$1 ORDER BY name", parsed_venue_id)
    return [dict(r) for r in rows]


@router.post("/venues/{venue_id}/screens")
async def create_screen(
    venue_id: str,
    body: ScreenCreate,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    parsed_venue_id = _parse_uuid(venue_id, "venue_id")
    venue_exists = await conn.fetchval("SELECT id FROM venues WHERE id=$1", parsed_venue_id)
    if not venue_exists:
        raise HTTPException(status_code=404, detail="Venue not found")

    try:
        async with conn.transaction():
            screen = await conn.fetchrow(
                "INSERT INTO screens (venue_id, name, capacity) VALUES ($1,$2,$3) RETURNING *",
                parsed_venue_id, body.name, body.capacity
            )
            screen_id = screen["id"]
            if body.rows and body.cols:
                await _generate_seats_for_screen(
                    conn, str(screen_id), body.rows, body.cols, max_seats=body.capacity
                )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=409,
            detail=f"A screen named '{body.name}' already exists for this venue."
        )
    return dict(screen)


# ---- Events ----
class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: str = "movie"
    duration_minutes: Optional[int] = None
    language: Optional[str] = None
    genre: Optional[str] = None
    poster_url: Optional[str] = None
    status: str = "draft"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Event title cannot be empty")
        return cleaned

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Duration must be greater than 0 minutes")
        return v

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        allowed = {"movie", "concert", "theatre", "other"}
        if v not in allowed:
            raise ValueError(f"Event type must be one of {sorted(allowed)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_event_status(cls, v: str) -> str:
        allowed = {"draft", "published", "inactive"}
        if v not in allowed:
            raise ValueError(f"Event status must be one of {sorted(allowed)}")
        return v


@router.get("/events")
async def list_events(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch("SELECT * FROM events ORDER BY created_at DESC")
    return [dict(r) for r in rows]


@router.post("/events")
async def create_event(
    body: EventCreate,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """INSERT INTO events (title, description, event_type, duration_minutes, language, genre, poster_url, status)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
        body.title, body.description, body.event_type, body.duration_minutes,
        body.language, body.genre, body.poster_url, body.status
    )
    return dict(row)


@router.patch("/events/{event_id}")
async def update_event(
    event_id: str,
    body: dict,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    parsed_event_id = _parse_uuid(event_id, "event_id")
    allowed = {"title", "description", "event_type", "duration_minutes", "language", "genre", "poster_url", "status"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    vals = list(updates.values())
    row = await conn.fetchrow(
        f"UPDATE events SET {set_clause}, updated_at=now() WHERE id=$1 RETURNING *",
        parsed_event_id, *vals
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return dict(row)


# ---- Shows ----
class ShowCreate(BaseModel):
    event_id: str
    screen_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    base_price: float
    status: str = "scheduled"

    @field_validator("base_price")
    @classmethod
    def validate_base_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Base price must be greater than 0")
        return round(v, 2)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"scheduled", "cancelled", "completed"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {sorted(allowed)}")
        return v


@router.get("/shows")
async def list_shows(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT s.*, e.title as event_title, v.name as venue_name, sc.name as screen_name
           FROM shows s
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           ORDER BY s.start_time DESC"""
    )
    return [dict(r) for r in rows]


@router.post("/shows")
async def create_show(
    body: ShowCreate,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    event_id = _parse_uuid(body.event_id, "event_id")
    screen_id = _parse_uuid(body.screen_id, "screen_id")

    event = await conn.fetchrow(
        "SELECT id, title, duration_minutes FROM events WHERE id=$1",
        event_id,
    )
    if not event:
        raise HTTPException(status_code=404, detail="Selected event not found")

    start_utc = _ensure_utc(body.start_time)
    if body.end_time is None:
        duration = event["duration_minutes"] or 120
        end_utc = start_utc + timedelta(minutes=duration + 15)
    else:
        end_utc = _ensure_utc(body.end_time)

    if end_utc <= start_utc:
        raise HTTPException(
            status_code=400,
            detail="Show end time must be strictly after start time."
        )

    async with conn.transaction():
        screen = await conn.fetchrow(
            """SELECT sc.id, sc.name, sc.capacity, v.name AS venue_name
               FROM screens sc
               JOIN venues v ON v.id = sc.venue_id
               WHERE sc.id = $1
               FOR UPDATE OF sc""",
            screen_id,
        )
        if not screen:
            raise HTTPException(status_code=404, detail="Selected screen not found")

        if body.status == "scheduled":
            conflict = await conn.fetchrow(
                """SELECT s.id, s.start_time, s.end_time, e.title AS event_title
                   FROM shows s
                   JOIN events e ON e.id = s.event_id
                   WHERE s.screen_id = $1
                     AND s.status = 'scheduled'
                     AND s.start_time < $3::timestamptz
                     AND s.end_time > $2::timestamptz
                   ORDER BY s.start_time ASC
                   LIMIT 1""",
                screen_id, start_utc, end_utc
            )
            if conflict:
                c_start = _ensure_utc(conflict["start_time"]).strftime("%Y-%m-%d %H:%M UTC")
                c_end = _ensure_utc(conflict["end_time"]).strftime("%Y-%m-%d %H:%M UTC")
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Scheduling conflict on '{screen['venue_name']} — {screen['name']}': "
                        f"overlaps with '{conflict['event_title']}' ({c_start} to {c_end})."
                    ),
                )

        show = await conn.fetchrow(
            """INSERT INTO shows
               (event_id, screen_id, start_time, end_time, base_price, status)
               VALUES ($1, $2, $3::timestamptz, $4::timestamptz, $5, $6)
               RETURNING *""",
            event_id,
            screen_id,
            start_utc,
            end_utc,
            body.base_price,
            body.status
        )
        show_id = show["id"]

        # Ensure the screen has physical seat rows before creating show_seats
        seat_count = await conn.fetchval("SELECT COUNT(*) FROM seats WHERE screen_id=$1", screen_id)
        if not seat_count and screen["capacity"] > 0:
            cols = min(10, screen["capacity"])
            rows_needed = (screen["capacity"] + cols - 1) // cols
            await _generate_seats_for_screen(
                conn, screen_id, rows_needed, cols, max_seats=screen["capacity"]
            )

        # Populate show_seats from screen seats atomically within the same transaction
        await conn.execute(
            """INSERT INTO show_seats (show_id, seat_id, price, status)
               SELECT $1, s.id, $2, 'available'
               FROM seats s WHERE s.screen_id=$3
               ON CONFLICT DO NOTHING""",
            show_id, body.base_price, screen_id
        )

    return dict(show)


@router.get("/shows/{show_id}")
async def get_show(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    parsed_show_id = _parse_uuid(show_id, "show_id")
    row = await conn.fetchrow(
        """SELECT s.*, e.title as event_title, e.duration_minutes, e.language, e.genre, e.poster_url,
                  v.name as venue_name, v.city, sc.name as screen_name, sc.capacity
           FROM shows s
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           WHERE s.id=$1""",
        parsed_show_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Show not found")
    return dict(row)


@router.delete("/shows/{show_id}")
async def delete_show(
    show_id: str,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    parsed_show_id = _parse_uuid(show_id, "show_id")
    try:
        deleted = await conn.fetchval("DELETE FROM shows WHERE id=$1 RETURNING id", parsed_show_id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete this show because bookings already exist for it."
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="Show not found")
    return {"message": "Show deleted"}
