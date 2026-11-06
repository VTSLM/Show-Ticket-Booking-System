from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncpg
from database import get_conn
from dependencies import require_role

router = APIRouter(prefix="/api/manager", tags=["manager"])

# ---- Venues ----
class VenueCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: str
    state: Optional[str] = None
    pincode: Optional[str] = None

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

@router.get("/venues/{venue_id}/screens")
async def list_screens(venue_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch("SELECT * FROM screens WHERE venue_id=$1 ORDER BY name", venue_id)
    return [dict(r) for r in rows]

@router.post("/venues/{venue_id}/screens")
async def create_screen(
    venue_id: str,
    body: ScreenCreate,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    screen = await conn.fetchrow(
        "INSERT INTO screens (venue_id, name, capacity) VALUES ($1,$2,$3) RETURNING *",
        venue_id, body.name, body.capacity
    )
    screen_id = screen["id"]
    # Auto-generate seats if rows/cols provided
    if body.rows and body.cols:
        import string
        row_labels = list(string.ascii_uppercase[:body.rows])
        for label in row_labels:
            for num in range(1, body.cols + 1):
                await conn.execute(
                    "INSERT INTO seats (screen_id, row_label, seat_number) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
                    screen_id, label, num
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
    allowed = {"title","description","event_type","duration_minutes","language","genre","poster_url","status"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    vals = list(updates.values())
    row = await conn.fetchrow(
        f"UPDATE events SET {set_clause}, updated_at=now() WHERE id=$1 RETURNING *",
        event_id, *vals
    )
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return dict(row)

# ---- Shows ----
class ShowCreate(BaseModel):
    event_id: str
    screen_id: str
    start_time: datetime
    end_time: datetime
    base_price: float
    status: str = "scheduled"

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
    show = await conn.fetchrow(
        """INSERT INTO shows
        (event_id, screen_id, start_time, end_time, base_price, status)
        VALUES ($1, $2, $3::timestamptz, $4::timestamptz, $5, $6)
        RETURNING *""",
        body.event_id,
        body.screen_id,
        body.start_time,
        body.end_time,
        body.base_price,
        body.status
    )
    show_id = show["id"]
    # Populate show_seats from screen seats
    await conn.execute(
        """INSERT INTO show_seats (show_id, seat_id, price, status)
           SELECT $1, s.id, $2, 'available'
           FROM seats s WHERE s.screen_id=(SELECT screen_id FROM shows WHERE id=$1)
           ON CONFLICT DO NOTHING""",
        show_id, body.base_price
    )
    return dict(show)

@router.get("/shows/{show_id}")
async def get_show(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    row = await conn.fetchrow(
        """SELECT s.*, e.title as event_title, e.duration_minutes, e.language, e.genre, e.poster_url,
                  v.name as venue_name, v.city, sc.name as screen_name, sc.capacity
           FROM shows s
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           WHERE s.id=$1""",
        show_id
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
    await conn.execute("DELETE FROM shows WHERE id=$1", show_id)
    return {"message": "Show deleted"}
