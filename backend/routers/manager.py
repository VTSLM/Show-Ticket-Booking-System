from datetime import datetime

import re
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import asyncpg
from database import get_conn
from dependencies import require_role

import json
import uuid

router = APIRouter(prefix="/api/manager", tags=["manager"])


def _is_admin(user: dict) -> bool:
    """get_current_user puts roles in a list; there is no single "role" key."""
    return "admin" in (user.get("roles") or [])


# ---- Ownership (issue #80) ----
# A manager owns an event through its organizer profile
# (events.organizer_id -> organizer_profiles.user_id), a show and its zones
# through the event, and a venue through the verification case they opened
# for it (venue_verification_cases.applicant_id). Admins own everything.
# Anything a manager does not own answers 404, so ids of other
# organizations' rows are not confirmed to exist.

MANAGER_ROLES = require_role("manager", "admin")

_OWNS_EVENT = """EXISTS (SELECT 1 FROM organizer_profiles op
                       WHERE op.id = {e}.organizer_id AND op.user_id = {uid})"""
_OWNS_VENUE = """EXISTS (SELECT 1 FROM venue_verification_cases vc
                       WHERE vc.venue_id = {v}.id AND vc.applicant_id = {uid})"""


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{what} not found")


def _require_uuid(value: str, what: str) -> None:
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise _not_found(what)


async def _assert_owns_event(conn, user: dict, event_id: str) -> None:
    _require_uuid(event_id, "Event")
    if _is_admin(user):
        return
    ok = await conn.fetchval(
        f"SELECT 1 FROM events e WHERE e.id = $1::uuid AND {_OWNS_EVENT.format(e='e', uid='$2')}",
        event_id, user["id"],
    )
    if not ok:
        raise _not_found("Event")


async def _assert_owns_show(conn, user: dict, show_id: str) -> None:
    _require_uuid(show_id, "Show")
    if _is_admin(user):
        return
    ok = await conn.fetchval(
        f"""SELECT 1 FROM shows s JOIN events e ON e.id = s.event_id
             WHERE s.id = $1::uuid AND {_OWNS_EVENT.format(e='e', uid='$2')}""",
        show_id, user["id"],
    )
    if not ok:
        raise _not_found("Show")


async def _assert_owns_venue(conn, user: dict, venue_id: str) -> None:
    _require_uuid(venue_id, "Venue")
    if _is_admin(user):
        return
    ok = await conn.fetchval(
        f"SELECT 1 FROM venues v WHERE v.id = $1::uuid AND {_OWNS_VENUE.format(v='v', uid='$2')}",
        venue_id, user["id"],
    )
    if not ok:
        raise _not_found("Venue")


async def _assert_owns_screen(conn, user: dict, screen_id: str) -> None:
    _require_uuid(screen_id, "Screen")
    if _is_admin(user):
        return
    ok = await conn.fetchval(
        f"""SELECT 1 FROM screens sc JOIN venues v ON v.id = sc.venue_id
             WHERE sc.id = $1::uuid AND {_OWNS_VENUE.format(v='v', uid='$2')}""",
        screen_id, user["id"],
    )
    if not ok:
        raise _not_found("Screen")


# ---- Venues ----
class VenueCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: str
    state: Optional[str] = None
    pincode: Optional[str] = None


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=30)
    percent_off: Decimal = Field(
        gt=0,
        lt=100,
        max_digits=5,
        decimal_places=2,
    )

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{3,30}", code):
            raise ValueError("Use 3–30 letters, numbers, hyphens, or underscores")
        return code


class CouponStatusUpdate(BaseModel):
    is_active: bool


@router.get("/venues")
async def list_venues(
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    # Managers see the venues they own plus approved venues, which they may
    # book for their shows (approved venues are already public via browse).
    if _is_admin(user):
        rows = await conn.fetch("SELECT v.*, true AS owned FROM venues v ORDER BY v.name")
    else:
        owns = _OWNS_VENUE.format(v="v", uid="$1")
        rows = await conn.fetch(
            f"""SELECT v.*, {owns} AS owned FROM venues v
                 WHERE {owns} OR v.verification_status = 'approved'
                 ORDER BY v.name""",
            user["id"],
        )
    return [dict(r) for r in rows]


@router.get("/coupons")
async def list_coupons(
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """SELECT id, code, discount_percent AS percent_off,
                  is_active, created_at
           FROM coupons
           WHERE event_id IS NULL
           ORDER BY created_at DESC"""
    )
    return [dict(row) for row in rows]


@router.post("/coupons")
async def create_coupon(
    body: CouponCreate,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        """INSERT INTO coupons
               (event_id, code, discount_percent, created_by)
           VALUES (NULL, $1, $2, $3)
           ON CONFLICT DO NOTHING
           RETURNING id, code, discount_percent AS percent_off,
                     is_active, created_at""",
        body.code,
        body.percent_off,
        user["id"],
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="A coupon with this code already exists",
        )
    return dict(row)


@router.patch("/coupons/{code}")
async def update_coupon_status(
    code: str,
    body: CouponStatusUpdate,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        """UPDATE coupons
           SET is_active = $2, updated_at = now()
           WHERE lower(code) = lower($1) AND event_id IS NULL
           RETURNING id, code, discount_percent AS percent_off,
                     is_active, created_at""",
        code.strip(),
        body.is_active,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return dict(row)
   


@router.post("/venues")
async def create_venue(
    body: VenueCreate,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    is_admin = _is_admin(user)
    v_status = "approved" if is_admin else "unverified"

    async with conn.transaction():
        row = await conn.fetchrow(
            """INSERT INTO venues (name, address, city, state, pincode, verification_status)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            body.name, body.address, body.city, body.state, body.pincode, v_status
        )
        if not is_admin:
            await conn.execute(
                """INSERT INTO venue_verification_cases (venue_id, applicant_id)
                   VALUES ($1, $2) ON CONFLICT DO NOTHING""",
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
    layout_config: Optional[dict] = None  # Custom coordinate geometry, sections, polygons

@router.get("/venues/{venue_id}/screens")
async def list_screens(
    venue_id: str,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    _require_uuid(venue_id, "Venue")
    if not _is_admin(user):
        visible = await conn.fetchval(
            f"""SELECT 1 FROM venues v WHERE v.id = $1::uuid
                 AND ({_OWNS_VENUE.format(v='v', uid='$2')} OR v.verification_status = 'approved')""",
            venue_id, user["id"],
        )
        if not visible:
            _not_found("Venue")
    rows = await conn.fetch("SELECT * FROM screens WHERE venue_id=$1::uuid ORDER BY name", venue_id)
    return [dict(r) for r in rows]

@router.post("/venues/{venue_id}/screens")
async def create_screen(
    venue_id: str,
    body: ScreenCreate,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_venue(conn, user, venue_id)
    cfg_json = json.dumps(body.layout_config) if body.layout_config else None
    screen = await conn.fetchrow(
        """INSERT INTO screens (venue_id, name, capacity, layout_type, stage_position, layout_config)
           VALUES ($1::uuid, $2, $3, $4, $5, $6) RETURNING *""",
        venue_id, body.name, body.capacity, body.layout_type or "cinema", body.stage_position or "front",
        cfg_json
    )
    screen_id = screen["id"]
    # Auto-generate seats if rows/cols provided with ultra-fast batch insertion and coordinate tracking
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
        for r_idx, label in enumerate(row_labels):
            stype = "premium" if (label in prem_rows or label.upper() in prem_rows) else "standard"
            y_coord = float(r_idx * 42 + 60)
            for num in range(1, body.cols + 1):
                x_coord = float((num - 1) * 38 + 50)
                seat_records.append((screen_id, label, num, stype, x_coord, y_coord, "Main Seating"))

        if seat_records:
            # Batch in chunks of 1000 to prevent timeouts and provide sub-second execution
            for i in range(0, len(seat_records), 1000):
                await conn.executemany(
                    """INSERT INTO seats (screen_id, row_label, seat_number, seat_type, x_pos, y_pos, section_name)
                       VALUES ($1, $2, $3, $4::seat_type, $5, $6, $7) ON CONFLICT DO NOTHING""",
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
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_screen(conn, user, screen_id)
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
    backdrop_url: Optional[str] = None
    status: str = "draft"
    organizer_id: Optional[str] = None
    cast_crew: Optional[List[dict]] = None
    artists: Optional[List[dict]] = None
    formats: Optional[List[str]] = None
    certificate: Optional[str] = "UA"
    release_date: Optional[str] = None
    terms_and_conditions: Optional[str] = None

def event_formats(event_type: Optional[str], formats: Optional[List[str]]) -> List[str]:
    """Cinema formats (2D, 3D, IMAX, 4DX) apply to movies only (#168).

    Movies keep the formats given, or 2D by default. Every other event type has none.
    """
    if (event_type or "movie").lower() != "movie":
        return []
    cleaned = [f.strip() for f in (formats or []) if isinstance(f, str) and f.strip()]
    return list(dict.fromkeys(cleaned)) or ["2D"]


@router.get("/events")
async def list_events(
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    admin = _is_admin(user)
    rows = await conn.fetch(
        """SELECT e.*, op.legal_name as organization_name, op.verification_status as organizer_status
           FROM events e
           LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
           WHERE $1::boolean OR op.user_id = $2
           ORDER BY e.created_at DESC""",
        admin, user["id"],
    )
    return [dict(r) for r in rows]

@router.post("/events")
async def create_event(
    body: EventCreate,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    organizer_id = body.organizer_id
    is_admin = _is_admin(user)

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

    cast_json = json.dumps(body.cast_crew) if body.cast_crew else "[]"
    artist_json = json.dumps(body.artists) if body.artists else "[]"
    rel_date = datetime.strptime(body.release_date, "%Y-%m-%d").date() if body.release_date else None

    row = await conn.fetchrow(
        """INSERT INTO events
           (title, description, event_type, duration_minutes, language, genre, poster_url,
            backdrop_url, status, organizer_id, cast_crew, artists, formats, certificate, release_date, terms_and_conditions)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::uuid,$11::jsonb,$12::jsonb,$13,$14,$15,$16)
           RETURNING *""",
        body.title, body.description, body.event_type, body.duration_minutes,
        body.language, body.genre, body.poster_url, body.backdrop_url, body.status, organizer_id,
        cast_json, artist_json, event_formats(body.event_type, body.formats), body.certificate or "UA", rel_date, body.terms_and_conditions
    )
    return dict(row)

@router.patch("/events/{event_id}")
async def update_event(
    event_id: str,
    body: dict,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_event(conn, user, event_id)
    allowed = {
        "title","description","event_type","duration_minutes","language","genre",
        "poster_url","backdrop_url","status","certificate","release_date",
        "terms_and_conditions","cast_crew","artists","formats"
    }
    updates = {}
    for k, v in body.items():
        if k in allowed:
            if k in ("cast_crew", "artists") and isinstance(v, (list, dict)):
                updates[k] = json.dumps(v)
            elif k == "release_date" and isinstance(v, str) and v.strip():
                updates[k] = datetime.strptime(v.strip(), "%Y-%m-%d").date()
            else:
                updates[k] = v

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    if "event_type" in updates or "formats" in updates:
        current = await conn.fetchrow("SELECT event_type, formats FROM events WHERE id=$1::uuid", event_id)
        if not current:
            raise HTTPException(status_code=404, detail="Event not found")
        updates["formats"] = event_formats(
            updates.get("event_type", current["event_type"]),
            updates.get("formats", current["formats"]),
        )
    set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(updates))
    vals = list(updates.values())
    row = await conn.fetchrow(
        f"UPDATE events SET {set_clause}, updated_at=now() WHERE id=$1::uuid RETURNING *",
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
    polygon_coords: Optional[list] = None
    x_pos: Optional[float] = None
    y_pos: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class ShowCreate(BaseModel):
    event_id: str
    screen_id: str
    start_time: datetime
    end_time: datetime
    base_price: float
    premium_multiplier: Optional[float] = 1.5
    dynamic_pricing: bool = False
    status: str = "scheduled"
    terms_and_conditions: Optional[str] = None
    zones: Optional[List[ZoneInput]] = None

@router.get("/shows")
async def list_shows(
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        f"""SELECT s.*, e.title as event_title, v.name as venue_name, sc.name as screen_name,
                  sc.layout_type
           FROM shows s
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           WHERE $1::boolean OR {_OWNS_EVENT.format(e='e', uid='$2')}
           ORDER BY s.start_time DESC""",
        _is_admin(user), user["id"],
    )
    return [dict(r) for r in rows]

@router.post("/shows")
async def create_show(
    body: ShowCreate,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    is_admin = _is_admin(user)

    # Double-Lock Verification Guard: Both Event Organizer AND Venue must be verified
    if not is_admin:
        guard_row = await conn.fetchrow(
            """SELECT e.title as event_title, e.organizer_id, op.user_id as org_user_id,
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

        # Managers may only schedule shows for their own organization's events.
        if str(guard_row["org_user_id"]) != str(user["id"]):
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
        (event_id, screen_id, start_time, end_time, base_price, status, terms_and_conditions, dynamic_pricing)
        VALUES ($1::uuid, $2::uuid, $3::timestamptz, $4::timestamptz, $5, $6, $7, $8)
        RETURNING *""",
        body.event_id,
        body.screen_id,
        body.start_time,
        body.end_time,
        body.base_price,
        body.status,
        body.terms_and_conditions,
        body.dynamic_pricing
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
            poly_json = json.dumps(z.polygon_coords) if z.polygon_coords else None
            await conn.execute(
                """INSERT INTO show_zones (show_id, name, zone_type, total_capacity, price, color_hex, display_order, polygon_coords, x_pos, y_pos, width, height)
                   VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12)""",
                show_id, z.name, z.zone_type or "standing", z.total_capacity, z.price, z.color_hex or "#287cff", idx,
                poly_json, z.x_pos, z.y_pos, z.width, z.height
            )

    return dict(show)

@router.get("/shows/{show_id}/zones")
async def list_show_zones(
    show_id: str,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _assert_owns_show(conn, user, show_id)
    rows = await conn.fetch(
        """SELECT * FROM show_zones WHERE show_id=$1::uuid ORDER BY display_order, price DESC""",
        show_id
    )
    return [dict(r) for r in rows]

@router.post("/shows/{show_id}/zones")
async def add_show_zone(
    show_id: str,
    body: ZoneInput,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_show(conn, user, show_id)
    poly_json = json.dumps(body.polygon_coords) if body.polygon_coords else None
    row = await conn.fetchrow(
        """INSERT INTO show_zones (show_id, name, zone_type, total_capacity, price, color_hex, polygon_coords, x_pos, y_pos, width, height)
           VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11) RETURNING *""",
        show_id, body.name, body.zone_type or "standing", body.total_capacity, body.price, body.color_hex or "#287cff",
        poly_json, body.x_pos, body.y_pos, body.width, body.height
    )
    return dict(row)

@router.delete("/shows/{show_id}/zones/{zone_id}")
async def delete_show_zone(
    show_id: str,
    zone_id: str,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_show(conn, user, show_id)
    _require_uuid(zone_id, "Zone")
    await conn.execute(
        """DELETE FROM show_zones WHERE id=$1::uuid AND show_id=$2::uuid""",
        zone_id, show_id
    )
    return {"deleted": True}

@router.get("/shows/{show_id}")
async def get_show(
    show_id: str,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _assert_owns_show(conn, user, show_id)
    row = await conn.fetchrow(
        """SELECT s.*, e.title as event_title, e.duration_minutes, e.language, e.genre, e.poster_url,
                  v.name as venue_name, v.city, sc.name as screen_name, sc.capacity
           FROM shows s
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           WHERE s.id=$1::uuid""",
        show_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Show not found")
    return dict(row)

@router.delete("/shows/{show_id}")
async def delete_show(
    show_id: str,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_show(conn, user, show_id)
    await conn.execute("DELETE FROM shows WHERE id=$1::uuid", show_id)
    return {"message": "Show deleted"}

@router.patch("/shows/{show_id}")
async def update_show(
    show_id: str,
    body: dict,
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_show(conn, user, show_id)
    allowed = {"start_time", "end_time", "base_price", "status", "dynamic_pricing"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    if "dynamic_pricing" in updates and not isinstance(updates["dynamic_pricing"], bool):
        raise HTTPException(status_code=400, detail="dynamic_pricing must be true or false")
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
    user: dict = Depends(MANAGER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    await _assert_owns_event(conn, user, event_id)
    await conn.execute("DELETE FROM events WHERE id=$1::uuid", event_id)
    return {"message": "Event deleted"}