from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import asyncpg
import io
from database import get_conn
from dependencies import get_current_user
from services.ticket_service import build_ticket_pdf
from services.qr_service import generate_qr_bytes
from services.email_service import send_ticket_email
from config import GMAIL_USER

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

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
           WHERE bs.booking_id=$1""",
        booking_id
    )
    return [dict(r) for r in rows]


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
        "start_time": str(booking["start_time"]),
        "seats": seats,
        "total_amount": float(booking["total_amount"]),
        "user_name": booking["user_name"],
        "user_email": booking["user_email"],
        "qr_b64": qr_b64,
    }
    try:
        print("========== EMAIL DEBUG ==========")
        print("SENDER:", GMAIL_USER)
        print("RECIPIENT:", ticket_data.get("user_email"))
        print("BOOKING:", ticket_data.get("booking_id"))
        print("EVENT:", ticket_data.get("event_title"))
        print("=================================")

        await send_ticket_email(ticket_data)

        print("EMAIL SEND FUNCTION COMPLETED SUCCESSFULLY")
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
        raise HTTPException(
            status_code=404,
            detail="Booking not found"
        )
    if booking["status"] != "confirmed":
        raise HTTPException(
            status_code=403,
            detail="Ticket PDF is only available after payment is complete"
        )

    qr_data = f"TICKETFLOW:{booking_id}"
    qr_b64 = generate_qr_bytes(qr_data)

    seats = await _get_booking_seats(booking_id, conn)

    ticket_data = {
        "booking_id": booking_id,
        "event_title": booking["event_title"],
        "venue_name": booking["venue_name"],
        "screen_name": booking["screen_name"],
        "start_time": str(booking["start_time"]),
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
            "Content-Disposition":
                f'attachment; filename="ticket_{booking_id[:8]}.pdf"'
        }
    )


@router.get("/bookings/{booking_id}/verify")
async def verify_ticket(booking_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    row = await conn.fetchrow("SELECT id, status, is_used FROM tickets WHERE booking_id=$1", booking_id)
    if not row:
        return {"valid": False, "message": "Ticket not found"}
    return {"valid": row["status"] == "valid" and not row["is_used"],
            "status": row["status"],
            "ticket_id": str(row["id"]),
            "used": row["is_used"]}
