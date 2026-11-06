"""
routers/bookings.py — F6: Ticket Generation & Verification

API surface:
  POST /bookings/confirm           → generate QR + PDF, send email, persist to DB
  GET  /bookings/{booking_id}/pdf  → download PDF ticket
  GET  /bookings/{booking_id}/verify → venue QR scan endpoint (marks ticket used)

DB layer:
  When SUPABASE_URL + SUPABASE_SERVICE_KEY are set, every confirmed ticket is
  persisted to the `tickets` table (run migration 002_tickets_f6.sql first).
  Without DB credentials the server runs in demo mode: in-memory dict, no
  data survives a restart.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
import os

from services.qr_service import generate_qr_base64
from services.ticket_service import build_ticket_pdf
from services.email_service import send_ticket_email
from services import db_service

router = APIRouter()


# ── Pydantic models ──────────────────────────────────────────────────────────

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


# ── In-memory fallback (used when DB is not configured) ─────────────────────
_mem: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mem_get(booking_id: str):
    return _mem.get(booking_id)

def _mem_set(booking_id: str, data: dict):
    _mem[booking_id] = data

def _build_ticket_data(payload: BookingPayload, qr_base64: str, email_sent: bool) -> dict:
    return {
        "booking_id":       payload.booking_id,
        "transaction_id":   payload.transaction_id,
        "user":             payload.user.model_dump(),
        "event":            payload.event.model_dump(),
        "seats":            [s.model_dump() for s in payload.seats],
        "total_amount":     payload.total_amount,
        "booked_at":        payload.booked_at,
        "qr_code_base64":   qr_base64,
        "email_sent":       email_sent,
        "pdf_download_url": f"/bookings/{payload.booking_id}/pdf",
        "is_used":          False,
        "used_at":          None,
    }


# ── POST /bookings/confirm ───────────────────────────────────────────────────

@router.post("/confirm")
async def confirm_booking(payload: BookingPayload):
    """
    Called after a successful payment.
    1. Validates payment_status == SUCCESS
    2. Idempotency check (DB or memory)
    3. Generates QR code + PDF ticket
    4. Sends confirmation email (non-blocking)
    5. Persists ticket to DB (falls back to memory if DB not configured)
    6. Returns ticket data to frontend
    """

    if payload.payment_status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Payment not successful")

    # ── Idempotency: check DB first, then memory ─────────────────────────
    db_row = db_service.get_ticket(payload.booking_id)
    if db_row:
        return JSONResponse(status_code=200, content={
            "status": "already_processed",
            **(_mem_get(payload.booking_id) or _db_row_to_response(db_row)),
        })

    mem_hit = _mem_get(payload.booking_id)
    if mem_hit:
        return JSONResponse(status_code=200, content={
            "status": "already_processed",
            **mem_hit,
        })

    # ── Build payload dict for services ─────────────────────────────────
    payload_dict = payload.model_dump()

    # ── Generate QR + PDF ────────────────────────────────────────────────
    qr_base64 = generate_qr_base64(payload.booking_id)
    pdf_bytes  = build_ticket_pdf(payload_dict)

    # ── Send email (failure is non-fatal) ────────────────────────────────
    email_sent = send_ticket_email(
        user_email=payload.user.email,
        user_name=payload.user.name,
        event_name=payload.event.name,
        booking_id=payload.booking_id,
        pdf_bytes=pdf_bytes,
    )

    # ── Persist to DB ────────────────────────────────────────────────────
    ticket_data = _build_ticket_data(payload, qr_base64, email_sent)
    db_saved    = db_service.save_ticket(payload_dict)

    if db_saved:
        # Merge any DB-generated fields (id, confirmed_at) into response
        ticket_data["db_id"]        = db_saved.get("id")
        ticket_data["confirmed_at"] = db_saved.get("confirmed_at")

    # Always keep a memory copy for the /pdf endpoint within this session
    _mem_set(payload.booking_id, ticket_data)

    return JSONResponse(status_code=201, content={
        "status": "confirmed",
        **ticket_data,
    })


# ── GET /bookings/{booking_id}/pdf ───────────────────────────────────────────

@router.get("/{booking_id}/pdf")
async def download_ticket_pdf(booking_id: str):
    """Download the PDF ticket by booking ID."""
    from fastapi.responses import Response

    # Try memory first (fast), then DB
    stored = _mem_get(booking_id)
    if stored is None:
        db_row = db_service.get_ticket(booking_id)
        if db_row:
            stored = _db_row_to_response(db_row)

    if stored is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    pdf_bytes = build_ticket_pdf(stored)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ticket_{booking_id}.pdf"'
        },
    )


# ── GET /bookings/{booking_id}/verify ────────────────────────────────────────

@router.get("/{booking_id}/verify")
async def verify_ticket(booking_id: str):
    """
    Venue QR scan endpoint.
    - First scan → marks ticket as used, returns status: valid
    - Second scan → returns status: already_used with timestamp
    - Unknown ID  → 404
    """

    # ── Try DB path ──────────────────────────────────────────────────────
    db_row = db_service.get_ticket(booking_id)

    if db_row:
        if db_row.get("is_used"):
            return JSONResponse(status_code=409, content={
                "status":     "already_used",
                "booking_id": booking_id,
                "used_at":    db_row.get("used_at"),
                "event":      _event_from_db(db_row),
                "user":       _user_from_db(db_row),
            })

        updated = db_service.mark_ticket_used(booking_id)
        if updated:
            return JSONResponse(status_code=200, content={
                "status":     "valid",
                "booking_id": booking_id,
                "used_at":    updated.get("used_at"),
                "event":      _event_from_db(db_row),
                "user":       _user_from_db(db_row),
                "seats":      db_row.get("seats", []),
            })
        # Race condition: another request marked it used between get and update
        db_row = db_service.get_ticket(booking_id)
        return JSONResponse(status_code=409, content={
            "status":     "already_used",
            "booking_id": booking_id,
            "used_at":    db_row.get("used_at") if db_row else None,
        })

    # ── Fall back to in-memory ────────────────────────────────────────────
    mem = _mem_get(booking_id)
    if mem is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if mem.get("is_used"):
        return JSONResponse(status_code=409, content={
            "status":     "already_used",
            "booking_id": booking_id,
            "used_at":    mem.get("used_at"),
            "event":      mem["event"],
            "user":       mem["user"],
        })

    used_at = datetime.now(timezone.utc).isoformat()
    mem["is_used"] = True
    mem["used_at"] = used_at

    return JSONResponse(status_code=200, content={
        "status":     "valid",
        "booking_id": booking_id,
        "used_at":    used_at,
        "event":      mem["event"],
        "user":       mem["user"],
        "seats":      mem["seats"],
    })


# ── Private helpers for DB row → response shape ──────────────────────────────

def _event_from_db(row: dict) -> dict:
    return {
        "event_id": row.get("event_id_str", ""),
        "name":     row.get("event_name", ""),
        "date":     row.get("event_date", ""),
        "time":     row.get("event_time", ""),
        "venue":    row.get("event_venue", ""),
    }

def _user_from_db(row: dict) -> dict:
    return {
        "user_id": row.get("user_id_str", ""),
        "name":    row.get("user_name", ""),
        "email":   row.get("user_email", ""),
    }

def _db_row_to_response(row: dict) -> dict:
    """Convert a DB ticket row back into the API response shape."""
    return {
        "booking_id":       row["booking_number"],
        "transaction_id":   row.get("transaction_id", ""),
        "user":             _user_from_db(row),
        "event":            _event_from_db(row),
        "seats":            row.get("seats", []),
        "total_amount":     float(row.get("total_amount", 0)),
        "booked_at":        row.get("booked_at", ""),
        "qr_code_base64":   generate_qr_base64(row["booking_number"]),
        "email_sent":       False,
        "pdf_download_url": f"/bookings/{row['booking_number']}/pdf",
        "is_used":          row.get("is_used", False),
        "used_at":          row.get("used_at"),
        "db_id":            row.get("id"),
        "confirmed_at":     row.get("confirmed_at"),
    }
