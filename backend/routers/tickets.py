from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncpg
import uuid as _uuid
import io
from database import get_conn
from dependencies import get_current_user, require_role
from services.ticket_service import build_ticket_pdf, format_show_datetime
from services.qr_service import generate_qr_bytes
from services.email_service import send_ticket_email
from services import ticket_transfer as transfers

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

SCANNER_ROLES = require_role("manager", "admin")


def _is_admin(user: dict) -> bool:
    return "admin" in (user.get("roles") or [])


class TicketScanRequest(BaseModel):
    qr_data: Optional[str] = None
    booking_id: Optional[str] = None


def _parse_booking_id(qr_data: Optional[str], booking_id: Optional[str]) -> str:
    raw = (booking_id or "").strip()
    if not raw and qr_data:
        cleaned = qr_data.strip()
        if cleaned.upper().startswith("TICKETFLOW:"):
            raw = cleaned.split(":", 1)[1].strip()
        else:
            raw = cleaned
    if not raw:
        raise HTTPException(status_code=400, detail="Missing booking_id or qr_data in request")
    try:
        _uuid.UUID(raw)
        return raw
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format in ticket QR code")


async def _scan_and_consume_ticket(booking_id: str, user: dict, conn: asyncpg.Connection) -> dict:
    async with conn.transaction():
        await conn.fetchval("SELECT id FROM bookings WHERE id = $1::uuid FOR UPDATE", booking_id)
        return await _scan_locked_ticket(booking_id, user, conn)


async def _scan_locked_ticket(booking_id: str, user: dict, conn: asyncpg.Connection) -> dict:
    row = await conn.fetchrow(
        """SELECT t.id, t.booking_id, t.status, t.is_used,
                  e.title as event_title, s.start_time, v.name as venue_name,
                  sc.name as screen_name, u.name as user_name, u.email as user_email,
                  (
                      EXISTS (
                          SELECT 1 FROM organizer_profiles op
                          WHERE op.id = e.organizer_id AND op.user_id = $2::uuid
                      )
                      OR
                      EXISTS (
                          SELECT 1 FROM venue_verification_cases vc
                          WHERE vc.venue_id = v.id AND vc.applicant_id = $2::uuid
                      )
                  ) AS is_owner
           FROM tickets t
           JOIN bookings b ON b.id = t.booking_id
           JOIN shows s ON s.id = t.show_id
           JOIN events e ON e.id = s.event_id
           JOIN screens sc ON sc.id = s.screen_id
           JOIN venues v ON v.id = sc.venue_id
           JOIN users u ON u.id = t.user_id
           WHERE t.booking_id = $1::uuid""",
        booking_id, user["id"]
    )

    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found for this booking")

    if not _is_admin(user) and not row["is_owner"]:
        raise HTTPException(status_code=404, detail="Ticket not found for this booking")

    if row["status"] == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Ticket has been cancelled and cannot be used for entry"
        )

    if row["is_used"] or row["status"] == "used":
        raise HTTPException(
            status_code=409,
            detail="Ticket has already been scanned and used. Duplicate entry is not permitted."
        )

    # Seats sent to friends have their own QR codes; this one only admits the rest.
    seat_count, seats_left = await transfers.seats_left_on_booking(conn, booking_id)
    zones_left = await transfers.zones_left_on_booking(conn, booking_id)
    if (seat_count or zones_left) and not seats_left and not any(z["quantity"] for z in zones_left):
        raise HTTPException(
            status_code=409,
            detail="All seats on this booking were transferred. Scan the QR codes the recipients hold."
        )

    # Atomically mark the ticket as used (prevents concurrent double-scanning)
    updated = await conn.fetchrow(
        """UPDATE tickets
           SET is_used = true, status = 'used', used_at = now()
           WHERE booking_id = $1::uuid AND is_used = false AND status = 'valid'
           RETURNING id, booking_id, status, is_used""",
        booking_id
    )

    if not updated:
        raise HTTPException(
            status_code=409,
            detail="Ticket was already scanned and consumed by another scanner"
        )
    await transfers.close_pending_for_booking(conn, booking_id)

    return {
        "success": True,
        "valid": True,
        "message": "Ticket validated successfully. Admitted for entry.",
        "ticket_id": str(updated["id"]),
        "booking_id": str(updated["booking_id"]),
        "status": updated["status"],
        "used": updated["is_used"],
        "seats": seats_left,
        "zones": [{k: z[k] for k in ("booking_zone_id", "name", "quantity")}
                  for z in zones_left if z["quantity"] > 0],
        "attendee": {
            "name": row["user_name"],
            "email": row["user_email"]
        },
        "event": {
            "title": row["event_title"],
            "venue": row["venue_name"],
            "screen": row["screen_name"],
            "start_time": format_show_datetime(row["start_time"]),
        }
    }


async def _get_full_booking(booking_id: str, user_id: str, conn: asyncpg.Connection) -> dict:
    row = await conn.fetchrow(
        """SELECT b.id, b.status, b.total_amount, b.show_id,
                  e.title as event_title, e.language, e.genre, e.poster_url,
                  s.start_time, v.name as venue_name, v.city,
                  sc.name as screen_name,
                  u.name as user_name, u.email as user_email
           FROM bookings b
           JOIN shows s ON s.id=b.show_id
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           JOIN users u ON u.id=b.user_id
           WHERE b.id=$1 AND b.user_id=$2""",
        booking_id, user_id
    )
    return dict(row) if row else None


async def _get_booking_seats(booking_id: str, conn: asyncpg.Connection) -> list:
    rows = await conn.fetch(
        """SELECT s.row_label, s.seat_number, s.seat_type, bs.unit_price as price
           FROM booking_seats bs
           JOIN show_seats ss ON ss.id=bs.show_seat_id
           JOIN seats s ON s.id=ss.seat_id
           WHERE bs.booking_id=$1
             AND NOT EXISTS (SELECT 1 FROM ticket_transfer_seats tts
                             JOIN ticket_transfers tt ON tt.id = tts.transfer_id
                             WHERE tts.booking_seat_id = bs.id AND tt.status = 'accepted')""",
        booking_id
    )
    seats = [dict(r) for r in rows]
    for zone in await transfers.zones_left_on_booking(conn, booking_id):
        if zone["quantity"] > 0:
            seats.append({
                "row_label": zone["name"],
                "seat_number": f" × {zone['quantity']}",
                "seat_type": "standing",
                "price": zone["unit_price"] * zone["quantity"],
            })
    return seats


@router.post("/bookings/{booking_id}/confirm")
async def confirm_and_generate_ticket(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    booking = await _get_full_booking(booking_id, user_id, conn)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["status"] != "confirmed":
        raise HTTPException(status_code=400, detail="Payment not completed yet. Complete payment first.")

    # Already generated?
    existing = await conn.fetchrow("SELECT id FROM tickets WHERE booking_id=$1", booking_id)
    if existing:
        return {"message": "Ticket already generated", "ticket_id": str(existing["id"])}

    qr_data = f"TICKETFLOW:{booking_id}"
    qr_b64 = generate_qr_bytes(qr_data)
    seats = await _get_booking_seats(booking_id, conn)

    ticket_id = await conn.fetchval(
        """INSERT INTO tickets (booking_id, user_id, show_id, qr_code_data, status)
           VALUES ($1,$2,$3,$4,'valid') RETURNING id""",
        booking_id, user_id, str(booking["show_id"]), qr_data
    )

    ticket_data = {
        "ticket_id": str(ticket_id),
        "booking_id": booking_id,
        "event_title": booking["event_title"],
        "venue_name": booking["venue_name"],
        "venue_city": booking["city"],
        "screen_name": booking["screen_name"],
        "start_time": format_show_datetime(booking["start_time"]),
        "seats": seats,
        "total_amount": float(booking["total_amount"]),
        "user_name": booking["user_name"],
        "user_email": booking["user_email"],
        "qr_b64": qr_b64,
    }
    try:
        await send_ticket_email(ticket_data)
    except Exception as e:
        print(f"Email failed (non-fatal): {e}")

    return {"message": "Ticket generated and emailed", "ticket_id": str(ticket_id)}


@router.get("/bookings/{booking_id}/pdf")
async def download_ticket_pdf(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    booking = await _get_full_booking(booking_id, user_id, conn)

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking["status"] != "confirmed":
        raise HTTPException(status_code=403, detail="Ticket PDF is only available after payment is complete")

    qr_data = f"TICKETFLOW:{booking_id}"
    qr_b64 = generate_qr_bytes(qr_data)
    seats = await _get_booking_seats(booking_id, conn)

    ticket_data = {
        "booking_id": booking_id,
        "event_title": booking["event_title"],
        "venue_name": booking["venue_name"],
        "screen_name": booking["screen_name"],
        "start_time": format_show_datetime(booking["start_time"]),
        "seats": seats,
        "total_amount": float(booking["total_amount"]),
        "user_name": booking["user_name"],
        "qr_b64": qr_b64,
    }

    pdf_bytes = build_ticket_pdf(ticket_data)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ticket_{booking_id[:8]}.pdf"'
        }
    )


@router.get("/bookings/{booking_id}/verify")
async def verify_ticket(
    booking_id: str,
    conn: asyncpg.Connection = Depends(get_conn)
):
    try:
        _uuid.UUID(booking_id)
    except ValueError:
        return {"valid": False, "message": "Invalid ticket ID format"}

    row = await conn.fetchrow(
        """SELECT id, status, is_used FROM tickets WHERE booking_id=$1::uuid""",
        booking_id
    )
    if not row:
        return {"valid": False, "message": "Ticket not found"}

    is_valid = row["status"] == "valid" and not row["is_used"]
    if row["is_used"] or row["status"] == "used":
        msg = "Ticket has already been scanned and used"
    elif row["status"] == "cancelled":
        msg = "Ticket has been cancelled"
    else:
        msg = "Ticket is valid and ready for entry"

    return {
        "valid": is_valid,
        "status": row["status"],
        "used": row["is_used"],
        "message": msg
    }


@router.post("/scan")
async def scan_ticket(
    body: TicketScanRequest,
    current_user: dict = Depends(SCANNER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    qr = (body.qr_data or "").strip()
    if not body.booking_id and qr.upper().startswith(transfers.TRANSFER_QR_PREFIX):
        try:
            return await transfers.scan_transfer_qr(conn, current_user, qr[len(transfers.TRANSFER_QR_PREFIX):])
        except transfers.TransferError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
    booking_id = _parse_booking_id(body.qr_data, body.booking_id)
    return await _scan_and_consume_ticket(booking_id, current_user, conn)


@router.post("/bookings/{booking_id}/scan")
async def scan_ticket_by_booking_id(
    booking_id: str,
    current_user: dict = Depends(SCANNER_ROLES),
    conn: asyncpg.Connection = Depends(get_conn)
):
    try:
        _uuid.UUID(booking_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")
    return await _scan_and_consume_ticket(booking_id, current_user, conn)
