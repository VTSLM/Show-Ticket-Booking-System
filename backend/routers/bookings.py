from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List
import os

from services.qr_service import generate_qr_base64
from services.ticket_service import build_ticket_pdf
from services.email_service import send_ticket_email

router = APIRouter()


# ── Pydantic models matching the agreed mock payload ────────────────────────

class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str

class EventInfo(BaseModel):
    event_id: str
    name: str
    date: str
    time: str
    venue: str

class SeatInfo(BaseModel):
    seat_id: str
    row: str
    number: int
    tier: str
    price: float

class BookingPayload(BaseModel):
    booking_id: str
    transaction_id: str
    user: UserInfo
    event: EventInfo
    seats: List[SeatInfo]
    total_amount: float
    payment_status: str
    booked_at: str


# ── In-memory store for demo (replace with DB in production) ────────────────
_confirmed_bookings: dict = {}


@router.post("/confirm")
async def confirm_booking(payload: BookingPayload):
    """
    Called by the payment service after a successful transaction.
    1. Validates payment_status == SUCCESS
    2. Idempotency check — returns existing ticket if already processed
    3. Generates QR code (base64 PNG)
    4. Builds PDF ticket
    5. Sends confirmation email with PDF attached
    6. Returns ticket data to frontend
    """

    if payload.payment_status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Payment not successful")

    # ── Idempotency ─────────────────────────────────────────────────────────
    if payload.booking_id in _confirmed_bookings:
        return JSONResponse(
            status_code=200,
            content={
                "status": "already_processed",
                **_confirmed_bookings[payload.booking_id]
            }
        )

    # ── Convert payload to dict for services ────────────────────────────────
    payload_dict = payload.model_dump()

    # ── Generate QR code ────────────────────────────────────────────────────
    qr_base64 = generate_qr_base64(payload.booking_id)

    # ── Build PDF ticket ────────────────────────────────────────────────────
    pdf_bytes = build_ticket_pdf(payload_dict)

    # ── Send email (non-blocking — failure doesn't break the flow) ──────────
    email_sent = send_ticket_email(
        user_email=payload.user.email,
        user_name=payload.user.name,
        event_name=payload.event.name,
        booking_id=payload.booking_id,
        pdf_bytes=pdf_bytes,
    )

    # ── Build response ───────────────────────────────────────────────────────
    ticket_data = {
        "booking_id": payload.booking_id,
        "transaction_id": payload.transaction_id,
        "user": payload_dict["user"],
        "event": payload_dict["event"],
        "seats": payload_dict["seats"],
        "total_amount": payload.total_amount,
        "booked_at": payload.booked_at,
        "qr_code_base64": qr_base64,   # frontend renders this directly
        "email_sent": email_sent,
        "pdf_download_url": f"/bookings/{payload.booking_id}/pdf",
    }

    _confirmed_bookings[payload.booking_id] = ticket_data

    return JSONResponse(status_code=201, content={"status": "confirmed", **ticket_data})


@router.get("/{booking_id}/pdf")
async def download_ticket_pdf(booking_id: str):
    """Download the PDF ticket by booking ID."""
    from fastapi.responses import Response

    if booking_id not in _confirmed_bookings:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Rebuild PDF (in production, fetch from DB/storage)
    stored = _confirmed_bookings[booking_id]
    pdf_bytes = build_ticket_pdf(stored)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=ticket_{booking_id}.pdf"
        }
    )


@router.get("/{booking_id}/verify")
async def verify_ticket(booking_id: str):
    """
    Ticket verification endpoint — used by venue staff when scanning the QR code.
    - Returns booking details if valid and not yet used
    - Marks ticket as used on first scan (one-time entry)
    - Returns 409 if already scanned
    - Returns 404 if booking not found
    """
    from datetime import datetime, timezone

    if booking_id not in _confirmed_bookings:
        raise HTTPException(status_code=404, detail="Ticket not found")

    booking = _confirmed_bookings[booking_id]

    # Already scanned — reject double entry
    if booking.get("is_used"):
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_used",
                "booking_id": booking_id,
                "used_at": booking.get("used_at"),
                "event": booking["event"],
                "user": booking["user"],
            }
        )

    # First scan — mark as used
    used_at = datetime.now(timezone.utc).isoformat()
    _confirmed_bookings[booking_id]["is_used"] = True
    _confirmed_bookings[booking_id]["used_at"] = used_at

    return JSONResponse(
        status_code=200,
        content={
            "status": "valid",
            "booking_id": booking_id,
            "used_at": used_at,
            "event": booking["event"],
            "user": booking["user"],
            "seats": booking["seats"],
        }
    )
