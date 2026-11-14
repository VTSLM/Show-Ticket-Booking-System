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
    user: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    is_admin = user.get("role") == "admin"
    v_status = "approved" if is_admin else "unverified"
    
    async with conn.transaction():
        row = await conn.fetchrow(
            """INSERT INTO venues (name, address, city, state, pincode, verification_status)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            body.name, body.address, body.city, body.state, body.pincode, v_status
        )
        if not is_admin:
            await conn.execute(
                """INSERT INTO venue_verification_cases (venue_id, applicant_id, status)
                   VALUES ($1, $2, 'DRAFT') ON CONFLICT DO NOTHING""",
                row["id"], user["id"]
            )
    return dict(row)

# ---- Screens ----
class ScreenCreate(BaseModel):
    name: str
    capacity: int
    rows: Optional[int] = None
    cols: Optional[int] = None
    layout_type: Optional[str] = "cinema"  # "cinema", "concert", "theatre", "other"
    stage_position: Optional[str] = "front"  # "front", "center", "end"
    premium_rows: Optional[List[str]] = None  # e.g. ["D", "E"] or ["A", "B"]

@router.get("/venues/{venue_id}/screens")
async def list_screens(venue_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch("SELECT * FROM screens WHERE venue_id=$1::uuid ORDER BY name", venue_id)
    return [dict(r) for r in rows]

@router.post("/venues/{venue_id}/screens")
async def create_screen(
    venue_id: str,
    body: ScreenCreate,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    screen = await conn.fetchrow(
        """INSERT INTO screens (venue_id, name, capacity, layout_type, stage_position)
           VALUES ($1::uuid, $2, $3, $4, $5) RETURNING *""",
        venue_id, body.name, body.capacity, body.layout_type or "cinema", body.stage_position or "front"
    )
    screen_id = screen["id"]
    # Auto-generate seats if rows/cols provided with ultra-fast batch insertion
    if body.rows and body.cols:
        def get_row_label(i: int) -> str:
            res = ""
            while i >= 0:
                res = chr(i % 26 + 65) + res
                i = i // 26 - 1
            return res

        row_labels = [get_row_label(i) for i in range(body.rows)]
        prem_rows = {r.strip().upper() for r in (body.premium_rows or []) if r.strip()}

        seat_records = []
        for label in row_labels:
            stype = "premium" if (label in prem_rows or label.upper() in prem_rows) else "standard"
            for num in range(1, body.cols + 1):
                seat_records.append((screen_id, label, num, stype))

        if seat_records:
            # Batch in chunks of 1000 to prevent timeouts and provide sub-second execution
            for i in range(0, len(seat_records), 1000):
                await conn.executemany(
                    """INSERT INTO seats (screen_id, row_label, seat_number, seat_type)
                       VALUES ($1, $2, $3, $4::seat_type) ON CONFLICT DO NOTHING""",
                    seat_records[i:i+1000]
                )
    return dict(screen)

class UpdateSeatTierRequest(BaseModel):
    seat_type: str = "premium"  # "standard", "premium", "accessible"
    row_label: Optional[str] = None
    seat_ids: Optional[List[str]] = None

@router.put("/screens/{screen_id}/seats/tier")
async def update_seat_tier(
    screen_id: str,
    body: UpdateSeatTierRequest,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    if body.row_label:
        await conn.execute(
            """UPDATE seats SET seat_type=$1::seat_type
               WHERE screen_id=$2::uuid AND row_label=$3""",
            body.seat_type, screen_id, body.row_label
        )
    elif body.seat_ids:
        await conn.execute(
            """UPDATE seats SET seat_type=$1::seat_type
               WHERE screen_id=$2::uuid AND id=ANY($3::uuid[])""",
            body.seat_type, screen_id, body.seat_ids
        )
    else:
        raise HTTPException(status_code=400, detail="Provide row_label or seat_ids")
    return {"status": "success", "seat_type": body.seat_type}

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
    organizer_id: Optional[str] = None

@router.get("/events")
async def list_events(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT e.*, op.legal_name as organization_name, op.verification_status as organizer_status
           FROM events e
           LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
           ORDER BY e.created_at DESC"""
    )
    return [dict(r) for r in rows]

@router.post("/events")
async def create_event(
    body: EventCreate,
    user: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    organizer_id = body.organizer_id
    is_admin = user.get("role") == "admin"

    if not is_admin:
        if not organizer_id:
            # If manager didn't pass organizer_id, find approved organization for this account
            approved_orgs = await conn.fetch(
                "SELECT id, legal_name FROM organizer_profiles WHERE user_id = $1 AND verification_status = 'APPROVED'",
                user["id"]
            )
            if not approved_orgs:
                raise HTTPException(
                    status_code=403,
                    detail="Organizer verification required: You must have an approved organization profile to list events. Complete verification at /verification/organizer."
                )
            organizer_id = str(approved_orgs[0]["id"])
        else:
            org = await conn.fetchrow(
                "SELECT id, verification_status, legal_name FROM organizer_profiles WHERE id = $1::uuid AND user_id = $2",
                organizer_id, user["id"]
            )
            if not org:
                raise HTTPException(status_code=404, detail="Selected organization profile not found for your account.")
            if org["verification_status"] != "APPROVED":
                raise HTTPException(
                    status_code=403,
                    detail=f"Organization '{org['legal_name']}' is not approved (status: {org['verification_status']}). Only approved organizations can host events."
                )

    row = await conn.fetchrow(
        """INSERT INTO events (title, description, event_type, duration_minutes, language, genre, poster_url, status, organizer_id)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::uuid) RETURNING *""",
        body.title, body.description, body.event_type, body.duration_minutes,
        body.language, body.genre, body.poster_url, body.status, organizer_id
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

# ---- Shows & Zones ----
class ZoneInput(BaseModel):
    name: str
    total_capacity: int
    price: float
    zone_type: Optional[str] = "standing"
    color_hex: Optional[str] = "#287cff"


class ShowCreate(BaseModel):
    event_id: str
    screen_id: str
    start_time: datetime
    end_time: datetime
    base_price: float
    premium_multiplier: Optional[float] = 1.5
    status: str = "scheduled"
    zones: Optional[List[ZoneInput]] = None

@router.get("/shows")
async def list_shows(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT s.*, e.title as event_title, v.name as venue_name, sc.name as screen_name,
                  sc.layout_type
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
    user: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    is_admin = user.get("role") == "admin"

    # Double-Lock Verification Guard: Both Event Organizer AND Venue must be verified
    if not is_admin:
        guard_row = await conn.fetchrow(
            """SELECT e.title as event_title, e.organizer_id,
                      op.legal_name as org_name, op.verification_status as org_status,
                      v.name as venue_name, v.verification_status as venue_status
               FROM events e
               LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
               JOIN screens sc ON sc.id = $1::uuid
               JOIN venues v ON v.id = sc.venue_id
               WHERE e.id = $2::uuid""",
            body.screen_id, body.event_id
        )
        if not guard_row:
            raise HTTPException(status_code=404, detail="Selected event or venue screen not found.")

        if guard_row["org_status"] != "APPROVED":
            raise HTTPException(
                status_code=403,
                detail=f"Cannot schedule show: Event '{guard_row['event_title']}' host organization '{guard_row['org_name'] or 'Unknown'}' is not verified (status: {guard_row['org_status'] or 'unverified'}). Complete organizer verification first."
            )

        if guard_row["venue_status"] != "approved":
            raise HTTPException(
                status_code=403,
                detail=f"Cannot schedule show: Venue '{guard_row['venue_name']}' is not verified (status: {guard_row['venue_status'] or 'unverified'}). Complete venue safety verification first."
            )

    show = await conn.fetchrow(
        """INSERT INTO shows
        (event_id, screen_id, start_time, end_time, base_price, status)
        VALUES ($1::uuid, $2::uuid, $3::timestamptz, $4::timestamptz, $5, $6)
        RETURNING *""",
        body.event_id,
        body.screen_id,
        body.start_time,
        body.end_time,
        body.base_price,
        body.status
    )
    show_id = show["id"]
    mult = body.premium_multiplier or 1.5

    # Populate show_seats from screen seats with tiered pricing (standard vs premium)
    await conn.execute(
        """INSERT INTO show_seats (show_id, seat_id, price, status)
           SELECT $1::uuid, s.id,
                  CASE WHEN s.seat_type = 'premium' THEN ROUND(($2::numeric * $3::numeric), 2) ELSE $2::numeric END,
                  'available'
           FROM seats s WHERE s.screen_id=(SELECT screen_id FROM shows WHERE id=$1::uuid)
           ON CONFLICT DO NOTHING""",
        show_id, body.base_price, mult
    )

    # If concert/event standing zones are provided, create them
    if body.zones:
        for idx, z in enumerate(body.zones, start=1):
            await conn.execute(
                """INSERT INTO show_zones (show_id, name, zone_type, total_capacity, price, color_hex, display_order)
                   VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)""",
                show_id, z.name, z.zone_type or "standing", z.total_capacity, z.price, z.color_hex or "#287cff", idx
            )

    return dict(show)

@router.get("/shows/{show_id}/zones")
async def list_show_zones(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT * FROM show_zones WHERE show_id=$1::uuid ORDER BY display_order, price DESC""",
        show_id
    )
    return [dict(r) for r in rows]

@router.post("/shows/{show_id}/zones")
async def add_show_zone(
    show_id: str,
    body: ZoneInput,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """INSERT INTO show_zones (show_id, name, zone_type, total_capacity, price, color_hex)
           VALUES ($1::uuid, $2, $3, $4, $5, $6) RETURNING *""",
        show_id, body.name, body.zone_type or "standing", body.total_capacity, body.price, body.color_hex or "#287cff"
    )
    return dict(row)

@router.delete("/shows/{show_id}/zones/{zone_id}")
async def delete_show_zone(
    show_id: str,
    zone_id: str,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await conn.execute(
        """DELETE FROM show_zones WHERE id=$1::uuid AND show_id=$2::uuid""",
        zone_id, show_id
    )
    return {"deleted": True}

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

@router.patch("/shows/{show_id}")
async def update_show(
    show_id: str,
    body: dict,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    allowed = {"start_time", "end_time", "base_price", "status"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    vals = list(updates.values())
    row = await conn.fetchrow(
        f"UPDATE shows SET {set_clause}, updated_at=now() WHERE id=$1::uuid RETURNING *",
        show_id, *vals
    )
    if not row:
        raise HTTPException(status_code=404, detail="Show not found")
    return dict(row)

@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    _: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await conn.execute("DELETE FROM events WHERE id=$1::uuid", event_id)
    return {"message": "Event deleted"}
