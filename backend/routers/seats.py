from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List
import asyncpg
import json
from datetime import datetime, timezone
from database import get_conn
from dependencies import get_current_user
from services.dynamic_pricing import get_show_pricing, apply_multiplier
from services.terms_service import resolve_show_terms

router = APIRouter(prefix="/api/seats", tags=["seats"])

# ---- WebSocket Connection Manager ----
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}  # show_id -> [ws]

    async def connect(self, show_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(show_id, []).append(ws)

    def disconnect(self, show_id: str, ws: WebSocket):
        if show_id in self.active:
            self.active[show_id].discard(ws) if isinstance(self.active[show_id], set) else \
                (self.active[show_id].remove(ws) if ws in self.active[show_id] else None)

    async def broadcast(self, show_id: str, message: dict):
        dead = []
        for ws in self.active.get(show_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(show_id, ws)

manager = ConnectionManager()


LOCK_DURATION_MINUTES = 10

# ---- REST endpoints ----
@router.get("/{show_id}/map")
async def get_seat_map(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    # Fetch screen and event layout metadata
    show_meta = await conn.fetchrow(
        """SELECT sc.layout_type, sc.stage_position, sc.layout_config,
                  sh.terms_and_conditions as show_terms,
                  e.terms_and_conditions as event_terms, e.event_type
           FROM shows sh
           JOIN screens sc ON sc.id = sh.screen_id
           JOIN events e ON e.id = sh.event_id
           WHERE sh.id = $1::uuid""",
        show_id
    )
    if not show_meta:
        raise HTTPException(status_code=404, detail="Show not found")

    # Release expired locks in DB before returning the map
    await conn.execute(
        """UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL, locked_price=NULL
           WHERE show_id=$1::uuid AND status='locked' AND locked_until < NOW()""",
        show_id
    )
    rows = await conn.fetch(
        """SELECT ss.id as show_seat_id, ss.status, ss.price, ss.locked_price,
                  s.row_label, s.seat_number, s.seat_type,
                  s.x_pos, s.y_pos, s.section_name
           FROM show_seats ss
           JOIN seats s ON s.id = ss.seat_id
           WHERE ss.show_id = $1::uuid
           ORDER BY s.row_label, s.seat_number""",
        show_id
    )

    zones = await conn.fetch(
        """SELECT id, name, zone_type, total_capacity, booked_count, locked_count,
                  price, color_hex, display_order,
                  polygon_coords, x_pos, y_pos, width, height,
                  GREATEST(0, total_capacity - booked_count - locked_count) as available_capacity
           FROM show_zones
           WHERE show_id = $1::uuid
           ORDER BY display_order""",
        show_id
    )

    layout_type = show_meta.get("layout_type") if show_meta and show_meta.get("layout_type") else (
        show_meta.get("event_type") if show_meta else "cinema"
    )
    stage_pos = show_meta.get("stage_position") if show_meta and show_meta.get("stage_position") else "front"
    event_type = show_meta.get("event_type") if show_meta else "movie"
    layout_cfg = show_meta.get("layout_config") if show_meta and show_meta.get("layout_config") else None
    if isinstance(layout_cfg, str):
        try:
            layout_cfg = json.loads(layout_cfg)
        except Exception:
            pass

    # Resolve active terms and conditions
    terms_text, terms_hash, is_default = resolve_show_terms(
        show_terms=show_meta.get("show_terms") if show_meta else None,
        event_terms=show_meta.get("event_terms") if show_meta else None
    )

    formatted_zones = []
    for z in zones:
        zd = dict(z)
        if isinstance(zd.get("polygon_coords"), str):
            try:
                zd["polygon_coords"] = json.loads(zd["polygon_coords"])
            except Exception:
                pass
        formatted_zones.append(zd)

    # Dynamic pricing: show the current price; a locked seat shows its frozen price
    pricing = await get_show_pricing(conn, show_id)
    seats = []
    for r in rows:
        seat = dict(r)
        locked_price = seat.pop("locked_price", None)
        seat["base_price"] = seat["price"]
        if pricing["dynamic"]:
            if seat["status"] == "locked" and locked_price is not None:
                seat["price"] = locked_price
            elif seat["status"] == "available":
                seat["price"] = apply_multiplier(seat["price"], pricing["multiplier"])
        seats.append(seat)

    return {
        "layout_type": layout_type,
        "stage_position": stage_pos,
        "event_type": event_type,
        "layout_config": layout_cfg,
        "terms_and_conditions": terms_text,
        "terms_hash": terms_hash,
        "is_default_terms": is_default,
        "zones": formatted_zones,
        "seats": seats,
        "pricing": {
            "dynamic": pricing["dynamic"],
            "multiplier": float(pricing["multiplier"]),
            "reasons": pricing["reasons"],
            "change_pct": pricing["change_pct"],
        },
    }


@router.get("/{show_id}/terms")
async def get_show_terms_endpoint(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    """
    Dedicated endpoint to fetch active terms and conditions for a specific show.
    """
    row = await conn.fetchrow(
        """SELECT sh.id as show_id, sh.terms_and_conditions as show_terms,
                  e.title as event_title, e.terms_and_conditions as event_terms,
                  v.name as venue_name, sh.start_time
           FROM shows sh
           JOIN events e ON e.id = sh.event_id
           JOIN screens sc ON sc.id = sh.screen_id
           JOIN venues v ON v.id = sc.venue_id
           WHERE sh.id = $1::uuid""",
        show_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Show not found")

    terms_text, terms_hash, is_default = resolve_show_terms(
        show_terms=row["show_terms"],
        event_terms=row["event_terms"]
    )
    return {
        "show_id": str(row["show_id"]),
        "event_title": row["event_title"],
        "venue_name": row["venue_name"],
        "start_time": row["start_time"].isoformat(),
        "terms_and_conditions": terms_text,
        "terms_hash": terms_hash,
        "is_default": is_default
    }


class LockRequest(BaseModel):
    seat_ids: List[str]


class ZoneLockRequest(BaseModel):
    zone_id: str
    quantity: int = 1


@router.post("/{show_id}/lock-zone")
async def lock_zone(
    show_id: str,
    req: ZoneLockRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    # Atomically check capacity and increment locked_count
    zone = await conn.fetchrow(
        """UPDATE show_zones
           SET locked_count = locked_count + $3
           WHERE id=$1::uuid AND show_id=$2::uuid AND (total_capacity - booked_count - locked_count) >= $3
           RETURNING *""",
        req.zone_id, show_id, req.quantity
    )
    if not zone:
        raise HTTPException(status_code=409, detail="Not enough tickets available in this zone")

    remaining = zone["total_capacity"] - zone["booked_count"] - zone["locked_count"]
    await manager.broadcast(show_id, {
        "type": "zone_update",
        "zone_id": str(zone["id"]),
        "available_capacity": remaining
    })

    return {
        "zone_id": str(zone["id"]),
        "name": zone["name"],
        "locked_quantity": req.quantity,
        "price": float(zone["price"]),
        "total_price": float(zone["price"] * req.quantity)
    }


@router.post("/{show_id}/release-zone")
async def release_zone(
    show_id: str,
    req: ZoneLockRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    zone = await conn.fetchrow(
        """UPDATE show_zones
           SET locked_count = GREATEST(0, locked_count - $3)
           WHERE id=$1::uuid AND show_id=$2::uuid
           RETURNING *""",
        req.zone_id, show_id, req.quantity
    )
    if zone:
        remaining = zone["total_capacity"] - zone["booked_count"] - zone["locked_count"]
        await manager.broadcast(show_id, {
            "type": "zone_update",
            "zone_id": str(zone["id"]),
            "available_capacity": remaining
        })
    return {"released": True}

@router.post("/{show_id}/lock")
async def lock_seats(
    show_id: str,
    req: LockRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    if not req.seat_ids:
        raise HTTPException(status_code=400, detail="No seats provided")
    user_id = str(current_user["id"])
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    locked_until = now + timedelta(minutes=LOCK_DURATION_MINUTES)

    # Try to lock requested seats
    locked = []
    failed = []
    for seat_id in req.seat_ids:
        result = await conn.execute(
            """UPDATE show_seats SET status='locked', locked_by=$3::uuid, locked_until=$4
               WHERE id=$1::uuid AND show_id=$2::uuid AND status='available'""",
            seat_id, show_id, user_id, locked_until
        )
        if result == "UPDATE 1":
            locked.append(seat_id)
        else:
            failed.append(seat_id)

    if failed:
        # Rollback
        if locked:
            await conn.execute(
                """UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL
                   WHERE id=ANY($1::uuid[]) AND locked_by=$2::uuid""",
                locked, user_id
            )
        raise HTTPException(status_code=409, detail=f"Seats unavailable: {failed}")

    # Freeze the price the customer pays (dynamic shows), or clear any old frozen price
    pricing = await get_show_pricing(conn, show_id)
    if pricing["dynamic"]:
        await conn.execute(
            """UPDATE show_seats SET locked_price = ROUND(price * $2::numeric, 2)
               WHERE id = ANY($1::uuid[])""",
            locked, pricing["multiplier"]
        )
    else:
        await conn.execute(
            "UPDATE show_seats SET locked_price = NULL WHERE id = ANY($1::uuid[])", locked
        )

    await manager.broadcast(show_id, {"type": "lock", "seat_ids": locked, "user_id": user_id})
    return {"locked": locked, "locked_until": locked_until.isoformat()}


@router.post("/{show_id}/release")
async def release_seats(
    show_id: str,
    req: LockRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    if req.seat_ids:
        await conn.execute(
            """UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL, locked_price=NULL
               WHERE id=ANY($1::uuid[]) AND show_id=$2::uuid AND locked_by=$3::uuid AND status='locked'""",
            req.seat_ids, show_id, user_id
        )
        await manager.broadcast(show_id, {"type": "release", "seat_ids": req.seat_ids})
    return {"released": req.seat_ids}


# ---- WebSocket ----
@router.websocket("/{show_id}/ws")
async def seat_ws(show_id: str, websocket: WebSocket):
    await manager.connect(show_id, websocket)
    try:
        while True:
            await websocket.receive_text()
            # Client can send pings or requests
    except WebSocketDisconnect:
        manager.disconnect(show_id, websocket)
