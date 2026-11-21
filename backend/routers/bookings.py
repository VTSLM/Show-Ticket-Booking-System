from fastapi import APIRouter, Depends, HTTPException
import uuid as uuid_module
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel
from typing import List, Optional
import asyncpg
from database import get_conn
from dependencies import get_current_user
from services.terms_service import record_terms_acceptance, resolve_show_terms

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class CreateBookingRequest(BaseModel):
    show_id: str
    seat_ids: Optional[List[str]] = None
    zone_id: Optional[str] = None
    zone_quantity: Optional[int] = None
    terms_accepted: Optional[bool] = False
    terms_hash: Optional[str] = None
    terms_text: Optional[str] = None
    coupon_code: Optional[str] = None


class AcceptTermsRequest(BaseModel):
    terms_hash: str
    terms_text: str


async def _price_with_coupon(
    conn: asyncpg.Connection,
    subtotal: Decimal,
    requested_code: Optional[str],
):
    subtotal = Decimal(str(subtotal)).quantize(Decimal("0.01"))
    code = (requested_code or "").strip().upper()

    if not code:
        return None, None, subtotal, Decimal("0.00"), subtotal

    coupon = await conn.fetchrow(
        """SELECT id, code, discount_percent
           FROM coupons
           WHERE lower(code) = lower($1)
             AND is_active = true
             AND event_id IS NULL""",
        code
    )
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid or inactive coupon code")

    discount = (
        subtotal * Decimal(str(coupon["discount_percent"])) / Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return coupon["id"], coupon["code"], subtotal, discount, subtotal - discount


@router.post("/{booking_id}/accept-terms")
async def accept_terms(
    booking_id: str,
    req: AcceptTermsRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    booking = await conn.fetchrow(
        "SELECT id, show_id, user_id FROM bookings WHERE id = $1::uuid AND user_id = $2::uuid",
        booking_id, user_id
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found for current user")

    show_meta = await conn.fetchrow(
        """SELECT sh.terms_and_conditions as show_terms, e.terms_and_conditions as event_terms
           FROM shows sh JOIN events e ON e.id = sh.event_id WHERE sh.id = $1::uuid""",
        booking["show_id"]
    )
    _, active_hash, _ = resolve_show_terms(
        show_meta.get("show_terms") if show_meta else None,
        show_meta.get("event_terms") if show_meta else None
    )

    if req.terms_hash != active_hash:
        raise HTTPException(
            status_code=409,
            detail="Terms and Conditions have changed. Please review and accept the latest version."
        )

    acceptance = await record_terms_acceptance(
        conn=conn,
        user_id=user_id,
        show_id=str(booking["show_id"]),
        terms_hash=req.terms_hash,
        terms_text=req.terms_text,
        booking_id=booking_id
    )
    return {
        "status": "accepted",
        "acceptance_id": str(acceptance["id"]),
        "accepted_at": acceptance["accepted_at"].isoformat(),
        "terms_hash": acceptance["terms_hash"]
    }


async def _insert_booking(
    conn: asyncpg.Connection,
    booking_number: str,
    user_id: str,
    show_id: str,
    subtotal: Decimal,
    discount: Decimal,
    coupon_id: Optional[uuid_module.UUID],
):
    total = subtotal - discount
    return await conn.fetchval(
        """INSERT INTO bookings
               (booking_number, user_id, show_id, status, subtotal_amount,
                discount_amount, coupon_id, total_amount)
           VALUES ($1, $2, $3, 'pending', $4, $5, $6, $7)
           RETURNING id""",
        booking_number, user_id, show_id, subtotal, discount, coupon_id, total
    )


@router.post("")
async def create_booking(
    req: CreateBookingRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    booking_number = f"TF-{datetime.now().strftime('%Y%m%d')}-{str(uuid_module.uuid4())[:6].upper()}"

    if req.zone_id and req.zone_quantity and req.zone_quantity > 0:
        zone = await conn.fetchrow(
            """SELECT * FROM show_zones WHERE id=$1::uuid AND show_id=$2::uuid""",
            req.zone_id, req.show_id
        )
        if not zone:
            raise HTTPException(status_code=404, detail="Selected zone not found")

        subtotal = Decimal(str(zone["price"])) * req.zone_quantity

        async with conn.transaction():
            coupon_id, coupon_code, subtotal, discount, total = await _price_with_coupon(
                conn, subtotal, req.coupon_code
            )

            updated = await conn.execute(
                """UPDATE show_zones
                   SET booked_count = booked_count + $3,
                       locked_count = GREATEST(0, locked_count - $3)
                   WHERE id=$1::uuid AND show_id=$2::uuid
                     AND (total_capacity - booked_count) >= $3""",
                req.zone_id, req.show_id, req.zone_quantity
            )
            if updated != "UPDATE 1":
                raise HTTPException(status_code=409, detail="Not enough tickets available in this zone")

            booking_id = await _insert_booking(
                conn, booking_number, user_id, req.show_id,
                subtotal, discount, coupon_id
            )
            await conn.execute(
                """INSERT INTO booking_zones (booking_id, zone_id, quantity, unit_price)
                   VALUES ($1, $2, $3, $4)""",
                booking_id, req.zone_id, req.zone_quantity, zone["price"]
            )
            if req.terms_accepted and req.terms_hash:
                await record_terms_acceptance(
                    conn=conn,
                    user_id=user_id,
                    show_id=req.show_id,
                    terms_hash=req.terms_hash,
                    terms_text=req.terms_text or "",
                    booking_id=str(booking_id)
                )

        return {
            "booking_id": str(booking_id),
            "booking_number": booking_number,
            "subtotal_amount": float(subtotal),
            "discount_amount": float(discount),
            "total_amount": float(total),
            "coupon_code": coupon_code,
            "status": "pending",
            "zone_name": zone["name"],
            "quantity": req.zone_quantity
        }

    if not req.seat_ids:
        raise HTTPException(status_code=400, detail="Either seat_ids or zone_id with quantity must be provided")

    seats = await conn.fetch(
        """SELECT ss.id, COALESCE(ss.locked_price, ss.price) AS price, ss.status, ss.locked_by
           FROM show_seats ss
           WHERE ss.id=ANY($1::uuid[]) AND ss.show_id=$2""",
        req.seat_ids, req.show_id
    )
    if len(seats) != len(req.seat_ids):
        raise HTTPException(status_code=400, detail="Some seats not found")
    for s in seats:
        if s["status"] != "locked" or str(s["locked_by"]) != user_id:
            raise HTTPException(status_code=409, detail=f"Seat {s['id']} is not locked by you")

    subtotal = sum((Decimal(str(s["price"])) for s in seats), Decimal("0"))

    async with conn.transaction():
        coupon_id, coupon_code, subtotal, discount, total = await _price_with_coupon(
            conn, subtotal, req.coupon_code
        )

        booking_id = await _insert_booking(
            conn, booking_number, user_id, req.show_id,
            subtotal, discount, coupon_id
        )
        for s in seats:
            await conn.execute(
                "INSERT INTO booking_seats (booking_id, show_seat_id, unit_price) VALUES ($1,$2,$3)",
                booking_id, s["id"], s["price"]
            )
        if req.terms_accepted and req.terms_hash:
            await record_terms_acceptance(
                conn=conn,
                user_id=user_id,
                show_id=req.show_id,
                terms_hash=req.terms_hash,
                terms_text=req.terms_text or "",
                booking_id=str(booking_id)
            )

    return {
        "booking_id": str(booking_id),
        "booking_number": booking_number,
        "subtotal_amount": float(subtotal),
        "discount_amount": float(discount),
        "total_amount": float(total),
        "coupon_code": coupon_code,
        "status": "pending"
    }


@router.post("/waitlist/{show_id}")
async def join_waitlist(
    show_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])

    async with conn.transaction():
        show = await conn.fetchrow(
            """SELECT s.id, s.status, e.status AS event_status,
                      (SELECT COUNT(*) FROM show_seats ss
                       WHERE ss.show_id = s.id AND ss.status = 'available') AS available_seats,
                      (SELECT COALESCE(SUM(
                           GREATEST(0, sz.total_capacity - sz.booked_count - sz.locked_count)
                       ), 0)
                       FROM show_zones sz WHERE sz.show_id = s.id) AS available_zone_capacity
               FROM shows s
               JOIN events e ON e.id = s.event_id
               WHERE s.id = $1::uuid
               FOR UPDATE OF s""",
            show_id
        )

        if not show or show["status"] != "scheduled" or show["event_status"] != "published":
            raise HTTPException(status_code=404, detail="Show not found or no longer available")

        available_seats = int(show["available_seats"] or 0)
        available_zone_capacity = int(show["available_zone_capacity"] or 0)
        if available_seats > 0 or available_zone_capacity > 0:
            raise HTTPException(status_code=409, detail="This show still has tickets available")

        existing = await conn.fetchrow(
            """SELECT id, created_at FROM show_waitlist
               WHERE show_id = $1::uuid AND user_id = $2::uuid AND status = 'waiting'""",
            show_id, user_id
        )

        if existing:
            position = await conn.fetchval(
                """SELECT COUNT(*) FROM show_waitlist
                   WHERE show_id = $1::uuid AND status = 'waiting'
                     AND (created_at, id) <= ($2, $3)""",
                show_id, existing["created_at"], existing["id"]
            )
            return {"status": "already_joined", "position": int(position)}

        entry = await conn.fetchrow(
            """INSERT INTO show_waitlist (show_id, user_id, status, created_at)
               VALUES ($1::uuid, $2::uuid, 'waiting', NOW())
               ON CONFLICT (show_id, user_id)
               DO UPDATE SET status = 'waiting', created_at = NOW()
               RETURNING id, created_at""",
            show_id, user_id
        )

        position = await conn.fetchval(
            """SELECT COUNT(*) FROM show_waitlist
               WHERE show_id = $1::uuid AND status = 'waiting'
                 AND (created_at, id) <= ($2, $3)""",
            show_id, entry["created_at"], entry["id"]
        )

    return {"status": "joined", "position": int(position)}


@router.get("/waitlist")
async def list_my_waitlist(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    rows = await conn.fetch(
        """SELECT w.id, w.show_id, w.created_at,
                  e.title AS event_title, s.start_time,
                  v.name AS venue_name, v.city,
                  (SELECT COUNT(*) FROM show_waitlist ahead
                   WHERE ahead.show_id = w.show_id AND ahead.status = 'waiting'
                     AND (ahead.created_at, ahead.id) <= (w.created_at, w.id)) AS position
           FROM show_waitlist w
           JOIN shows s ON s.id = w.show_id
           JOIN events e ON e.id = s.event_id
           JOIN screens sc ON sc.id = s.screen_id
           JOIN venues v ON v.id = sc.venue_id
           WHERE w.user_id = $1::uuid AND w.status = 'waiting'
           ORDER BY w.created_at, w.id""",
        str(current_user["id"])
    )
    return [dict(row) for row in rows]


@router.delete("/waitlist/{show_id}")
async def leave_waitlist(
    show_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    result = await conn.execute(
        """UPDATE show_waitlist SET status = 'cancelled'
           WHERE show_id = $1::uuid AND user_id = $2::uuid AND status = 'waiting'""",
        show_id, str(current_user["id"])
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Active waitlist entry not found")
    return {"status": "cancelled"}


@router.get("/{booking_id}")
async def get_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """SELECT b.*,
                  MAX(c.code) AS coupon_code,
                  e.title        AS event_title,
                  e.poster_url,
                  sh.start_time,
                  sh.end_time,
                  e.duration_minutes,
                  v.name         AS venue_name,
                  v.city,
                  v.address,
                  sc.name        AS screen_name,
                  array_agg(row_to_json(bs.*)) AS seats_info
           FROM bookings b
           JOIN shows     sh ON sh.id = b.show_id
           JOIN events    e  ON e.id  = sh.event_id
           JOIN screens   sc ON sc.id = sh.screen_id
           JOIN venues    v  ON v.id  = sc.venue_id
           LEFT JOIN coupons c ON c.id = b.coupon_id
           LEFT JOIN (
             SELECT bs2.booking_id, ss.id AS show_seat_id,
                    s.row_label, s.seat_number, s.seat_type, ss.price
             FROM booking_seats bs2
             JOIN show_seats ss ON ss.id = bs2.show_seat_id
             JOIN seats      s  ON s.id  = ss.seat_id
           ) bs ON bs.booking_id = b.id
           WHERE b.id = $1 AND b.user_id = $2
           GROUP BY b.id, e.title, e.poster_url, sh.start_time, sh.end_time,
                    e.duration_minutes, v.name, v.city, v.address, sc.name""",
        booking_id, str(current_user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    import json
    result = dict(row)
    raw = result.get("seats_info") or []
    result["seats_info"] = [json.loads(s) if isinstance(s, str) else s for s in raw if s]
    return result


@router.get("")
async def list_my_bookings(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    rows = await conn.fetch(
        """SELECT b.id, b.status, b.total_amount, b.created_at,
                  b.cancellation_reason, b.refund_amount, b.refund_status,
                  e.title as event_title, e.poster_url,
                  s.start_time, v.name as venue_name, v.city,
                  COUNT(bs.show_seat_id) as seat_count
           FROM bookings b
           JOIN shows s ON s.id=b.show_id
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           LEFT JOIN booking_seats bs ON bs.booking_id=b.id
           WHERE b.user_id=$1
           GROUP BY b.id, e.id, s.id, v.id
           ORDER BY b.created_at DESC""",
        str(current_user["id"])
    )
    return [dict(r) for r in rows]