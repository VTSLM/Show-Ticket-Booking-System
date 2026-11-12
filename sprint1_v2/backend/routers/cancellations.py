"""
Ticket cancellation & refund endpoints.

PATCH /api/bookings/{booking_id}/cancel-eligibility  — check if cancellable
POST  /api/bookings/{booking_id}/cancel              — cancel + trigger refund
"""
from datetime import datetime, timezone, timedelta

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from database import get_conn
from dependencies import get_current_user
from services.refund_service import initiate_razorpay_refund

router = APIRouter(prefix="/api/bookings", tags=["cancellations"])

# Policy: cannot cancel if the show starts within this many hours
CANCEL_CUTOFF_HOURS = 2


# ── helpers ──────────────────────────────────────────────────────────────────

async def _fetch_booking_for_cancel(
    booking_id: str, user_id: str, conn: asyncpg.Connection
) -> dict:
    row = await conn.fetchrow(
        """
        SELECT b.id, b.status, b.total_amount, b.show_id,
               s.start_time,
               p.id              AS payment_id,
               p.status          AS payment_status,

               p.transaction_id,
               p.amount          AS paid_amount
        FROM bookings b
        JOIN shows s ON s.id = b.show_id
        LEFT JOIN payments p
               ON p.booking_id = b.id AND p.status = 'successful'
        WHERE b.id = $1 AND b.user_id = $2
        """,
        booking_id,
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")
    return dict(row)


def _cancellable(booking: dict) -> tuple[bool, str]:
    """Return (eligible, reason_if_not)."""
    if booking["status"] != "confirmed":
        return False, f"Booking is already {booking['status']}"

    now = datetime.now(timezone.utc)
    cutoff = booking["start_time"] - timedelta(hours=CANCEL_CUTOFF_HOURS)
    if now >= cutoff:
        return (
            False,
            f"Cannot cancel within {CANCEL_CUTOFF_HOURS} hours of show start",
        )

    return True, ""


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{booking_id}/cancel-eligibility")
async def check_cancel_eligibility(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Returns whether this booking can still be cancelled and how much would be refunded.
    Safe to call repeatedly — read-only.
    """
    booking = await _fetch_booking_for_cancel(
        booking_id, str(current_user["id"]), conn
    )
    eligible, reason = _cancellable(booking)

    if not eligible:
        return {"eligible": False, "reason": reason}

    cutoff = booking["start_time"] - timedelta(hours=CANCEL_CUTOFF_HOURS)
    return {
        "eligible": True,
        "refund_amount": float(booking["total_amount"]),
        "has_payment": booking["payment_id"] is not None,
        "show_start_time": booking["start_time"].isoformat(),
        "cancel_before": cutoff.isoformat(),
    }


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Cancel a confirmed booking.

    1. Validates eligibility (confirmed + > 2 h before show).
    2. In a single transaction:
       - booking  → cancelled
       - ticket   → cancelled
       - seats    → available
       - payment  → refunded (status + amounts)
    3. Outside the transaction (best-effort): calls Razorpay refund API
       and stores the rfnd_... ID.  A Razorpay failure does NOT roll back
       the cancellation — the refund can be retried manually from the
       Razorpay dashboard.
    """
    booking = await _fetch_booking_for_cancel(
        booking_id, str(current_user["id"]), conn
    )
    eligible, reason = _cancellable(booking)
    if not eligible:
        raise HTTPException(status_code=400, detail=reason)

    # ── atomic DB update ──────────────────────────────────────────────────
    async with conn.transaction():
        await conn.execute(
            """UPDATE bookings
               SET status = 'cancelled', cancelled_at = now(), updated_at = now()
               WHERE id = $1""",
            booking_id,
        )
        await conn.execute(
            "UPDATE tickets SET status = 'cancelled' WHERE booking_id = $1",
            booking_id,
        )
        await conn.execute(
            """UPDATE show_seats
               SET status = 'available', locked_by = NULL, locked_until = NULL
               WHERE id IN (
                   SELECT show_seat_id FROM booking_seats WHERE booking_id = $1
               )""",
            booking_id,
        )
        if booking["payment_id"]:
            await conn.execute(
                """UPDATE payments
                   SET status = 'refunded',
                       refunded_amount = $1,
                       refunded_at = now()
                   WHERE id = $2""",
                booking["paid_amount"],
                booking["payment_id"],
            )

    # ── Razorpay refund (best-effort, outside transaction) ────────────────
    refund_id = None
    rz_payment_id = booking["transaction_id"]

    if booking["payment_id"] and rz_payment_id:
        try:
            amount_paise = int(float(booking["paid_amount"]) * 100)
            refund_id = await initiate_razorpay_refund(rz_payment_id, amount_paise)
            await conn.execute(
                "UPDATE payments SET razorpay_refund_id = $1 WHERE id = $2",
                refund_id,
                booking["payment_id"],
            )
        except Exception as exc:
            print(f"[cancel] Razorpay refund call failed (manual follow-up needed): {exc}")

    return {
        "status": "cancelled",
        "refund_initiated": refund_id is not None,
        "refund_amount": float(booking["total_amount"]) if booking["payment_id"] else 0.0,
        "razorpay_refund_id": refund_id,
        "note": (
            "Refund initiated via Razorpay. Allow 5–7 business days."
            if refund_id
            else "No payment on record — booking cancelled with no charge."
            if not booking["payment_id"]
            else "Booking cancelled. Refund could not be auto-initiated — contact support."
        ),
    }
