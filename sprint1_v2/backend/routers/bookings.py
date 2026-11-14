from fastapi import APIRouter, Depends, HTTPException
import uuid as uuid_module
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
import asyncpg
from database import get_conn
from dependencies import get_current_user

router = APIRouter(prefix="/api/bookings", tags=["bookings"])

class CreateBookingRequest(BaseModel):
    show_id: str
    seat_ids: Optional[List[str]] = None  # show_seat_ids
    zone_id: Optional[str] = None
    zone_quantity: Optional[int] = None

@router.post("")
async def create_booking(
    req: CreateBookingRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    booking_number = f"TF-{datetime.now().strftime('%Y%m%d')}-{str(uuid_module.uuid4())[:6].upper()}"

    # Mode 1: Zone Booking (Concerts / Standing / Passes)
    if req.zone_id and req.zone_quantity and req.zone_quantity > 0:
        zone = await conn.fetchrow(
            """SELECT * FROM show_zones WHERE id=$1::uuid AND show_id=$2::uuid""",
            req.zone_id, req.show_id
        )
        if not zone:
            raise HTTPException(status_code=404, detail="Selected zone not found")

        total = float(zone["price"]) * req.zone_quantity

        async with conn.transaction():
            # Atomically decrement locked/increase booked
            updated = await conn.execute(
                """UPDATE show_zones
                   SET booked_count = booked_count + $3,
                       locked_count = GREATEST(0, locked_count - $3)
                   WHERE id=$1::uuid AND (total_capacity - booked_count) >= $3""",
                req.zone_id, req.show_id, req.zone_quantity
            )
            if updated != "UPDATE 1":
                raise HTTPException(status_code=409, detail="Not enough tickets available in this zone")

            booking_id = await conn.fetchval(
                """INSERT INTO bookings (booking_number, user_id, show_id, status, total_amount)
                   VALUES ($1, $2, $3, 'pending', $4) RETURNING id""",
                booking_number, user_id, req.show_id, total
            )
            await conn.execute(
                """INSERT INTO booking_zones (booking_id, zone_id, quantity, unit_price)
                   VALUES ($1, $2, $3, $4)""",
                booking_id, req.zone_id, req.zone_quantity, zone["price"]
            )

        return {
            "booking_id": str(booking_id),
            "booking_number": booking_number,
            "total_amount": float(total),
            "status": "pending",
            "zone_name": zone["name"],
            "quantity": req.zone_quantity
        }

    # Mode 2: Reserved Seat Booking (Cinema, Theatre, Stadium)
    if not req.seat_ids:
        raise HTTPException(status_code=400, detail="Either seat_ids or zone_id with quantity must be provided")

    # Verify all seats are locked by this user
    seats = await conn.fetch(
        """SELECT ss.id, ss.price, ss.status, ss.locked_by
           FROM show_seats ss
           WHERE ss.id=ANY($1::uuid[]) AND ss.show_id=$2""",
        req.seat_ids, req.show_id
    )
    if len(seats) != len(req.seat_ids):
        raise HTTPException(status_code=400, detail="Some seats not found")
    for s in seats:
        if s["status"] != "locked" or str(s["locked_by"]) != user_id:
            raise HTTPException(status_code=409, detail=f"Seat {s['id']} is not locked by you")

    total = sum(s["price"] for s in seats)

    async with conn.transaction():
        booking_id = await conn.fetchval(
            """INSERT INTO bookings (booking_number, user_id, show_id, status, total_amount)
               VALUES ($1,$2,$3,'pending',$4) RETURNING id""",
            booking_number, user_id, req.show_id, total
        )
        for s in seats:
            await conn.execute(
                "INSERT INTO booking_seats (booking_id, show_seat_id, unit_price) VALUES ($1,$2,$3)",
                booking_id, s["id"], s["price"]
            )

    return {"booking_id": str(booking_id), "booking_number": booking_number, "total_amount": float(total), "status": "pending"}


@router.get("/{booking_id}")
async def get_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """SELECT b.*,
                  e.title        AS event_title,
                  e.poster_url,
                  sh.start_time,
                  v.name         AS venue_name,
                  v.city,
                  sc.name        AS screen_name,
                  array_agg(row_to_json(bs.*)) AS seats_info
           FROM bookings b
           JOIN shows     sh ON sh.id = b.show_id
           JOIN events    e  ON e.id  = sh.event_id
           JOIN screens   sc ON sc.id = sh.screen_id
           JOIN venues    v  ON v.id  = sc.venue_id
           LEFT JOIN (
             SELECT bs2.booking_id, ss.id AS show_seat_id,
                    s.row_label, s.seat_number, s.seat_type, ss.price
             FROM booking_seats bs2
             JOIN show_seats ss ON ss.id = bs2.show_seat_id
             JOIN seats      s  ON s.id  = ss.seat_id
           ) bs ON bs.booking_id = b.id
           WHERE b.id = $1 AND b.user_id = $2
           GROUP BY b.id, e.title, e.poster_url, sh.start_time,
                    v.name, v.city, sc.name""",
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
