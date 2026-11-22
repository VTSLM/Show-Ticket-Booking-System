"""
Complete, production-ready Booking Cancellation, Refund Management & Webhook endpoints.
Customer, Administrator, and Razorpay Gateway lifecycle operations.
"""
import json
import logging
from typing import Optional
import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Header
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user, require_role
from config import RAZORPAY_WEBHOOK_SECRET
from services.ticket_transfer import close_pending_for_booking, has_accepted_transfers
from services.cancellation_policy_service import (
    get_show_cancellation_policy,
    evaluate_cancellation_eligibility,
)
from services.refund_service import (
    initiate_razorpay_refund,
    refund_and_record,
    verify_razorpay_webhook_signature,
)
from services.cancellation_notification_service import (
    create_notification,
    notify_admins,
    send_cancellation_email,
    send_refund_status_email,
)

require_admin = require_role("admin")

router = APIRouter(prefix="/api/bookings", tags=["cancellations"])
logger = logging.getLogger("uvicorn.error")

CANCEL_CUTOFF_HOURS = 2


# ── Schemas ───────────────────────────────────────────────────────────────────

class CancelBookingRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=150)
    comments: Optional[str] = Field(None, max_length=500)


class RetryRefundRequest(BaseModel):
    notes: Optional[str] = None


# ── Helper Query ──────────────────────────────────────────────────────────────

async def _fetch_booking_for_cancellation(
    booking_id: str, user_id: Optional[str], conn: asyncpg.Connection, for_update: bool = False
) -> dict:
    lock_clause = "FOR UPDATE OF b" if for_update else ""
    query = f"""
        SELECT b.id, b.status, b.total_amount, b.show_id, b.user_id,
               b.cancellation_reason, b.cancellation_notes, b.cancellation_charge,
               b.refund_amount, b.refund_status, b.cancelled_at,
               s.start_time, s.cancellation_policy_id,
               e.title AS event_title, e.poster_url,
               v.name AS venue_name, v.city AS venue_city,
               u.name AS user_name, u.email AS user_email,
               p.id AS payment_id, p.status AS payment_status,
               p.transaction_id, p.amount AS paid_amount,
               p.razorpay_refund_id, p.refunded_amount, p.refunded_at
        FROM bookings b
        JOIN shows s ON s.id = b.show_id
        JOIN events e ON e.id = s.event_id
        JOIN screens sc ON sc.id = s.screen_id
        JOIN venues v ON v.id = sc.venue_id
        JOIN users u ON u.id = b.user_id
        LEFT JOIN payments p ON p.booking_id = b.id AND p.status IN ('successful', 'refunded')
        WHERE b.id = $1::uuid
        {lock_clause}
    """
    row = await conn.fetchrow(query, booking_id)
    if not row:
        raise HTTPException(status_code=404, detail="Booking not found")

    if user_id and ("user_id" in row) and row["user_id"] and str(row["user_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="Unauthorized access to this booking")

    booking_dict = dict(row)

    # Safely fetch seats info if conn.fetch is awaitable
    booking_dict["seats_info"] = []
    if hasattr(conn, "fetch") and callable(getattr(conn, "fetch", None)):
        try:
            import inspect
            res = conn.fetch(
                """
                SELECT ss.id, st.row_label, st.seat_number, st.seat_type, bs.unit_price AS price
                FROM booking_seats bs
                JOIN show_seats ss ON ss.id = bs.show_seat_id
                JOIN seats st ON st.id = ss.seat_id
                WHERE bs.booking_id = $1::uuid
                ORDER BY st.row_label, st.seat_number
                """,
                booking_id,
            )
            if inspect.isawaitable(res):
                seats = await res
                if seats:
                    booking_dict["seats_info"] = [dict(s) for s in seats]
        except Exception:
            booking_dict["seats_info"] = []

    # Standing / general-admission passes are stored per zone, not per seat.
    booking_dict["zone_tickets"] = 0
    if hasattr(conn, "fetchval") and callable(getattr(conn, "fetchval", None)):
        try:
            import inspect
            res = conn.fetchval(
                "SELECT COALESCE(SUM(quantity), 0) FROM booking_zones WHERE booking_id = $1::uuid",
                booking_id,
            )
            if inspect.isawaitable(res):
                count = await res
                booking_dict["zone_tickets"] = int(count) if isinstance(count, (int, float)) else 0
        except Exception:
            booking_dict["zone_tickets"] = 0

    booking_dict["refund_info"] = None
    return booking_dict


# ── Customer Endpoints ────────────────────────────────────────────────────────

@router.get("/{booking_id}/cancel-eligibility")
@router.patch("/{booking_id}/cancel-eligibility")
async def check_cancel_eligibility(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Evaluates cancellation eligibility and returns full refund breakdown under active policy.
    Supports both GET and PATCH for compatibility.
    Read-only & safe to call repeatedly.
    """
    booking = await _fetch_booking_for_cancellation(
        booking_id, str(current_user["id"]), conn
    )
    policy = await get_show_cancellation_policy(conn, str(booking["show_id"]))
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, policy)

    seats_list = [f"{s['row_label']}{s['seat_number']}" for s in booking.get("seats_info", [])]

    return {
        "eligible": eligible,
        "cancellable": eligible,
        "reason": reason,
        "event_title": booking["event_title"],
        "venue_name": booking["venue_name"],
        "venue_city": booking["venue_city"],
        "start_time": booking["start_time"].isoformat() if booking["start_time"] else None,
        "seats": seats_list,
        "total_seats": len(seats_list) + int(booking.get("zone_tickets") or 0),
        "total_paid": float(booking.get("paid_amount") or booking.get("total_amount") or 0.0),
        "breakdown": breakdown,
    }


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
    req: Optional[CancelBookingRequest] = None,
):
    """
    Executes transaction-safe cancellation:
    1. Locks booking row with FOR UPDATE against concurrent cancellations.
    2. Verifies eligibility under active policy.
    3. Updates status to 'cancelled' and records reason and breakdown.
    4. Releases reserved show seats atomically.
    5. Initiates Razorpay refund (or schedules background task) and logs refund record.
    6. Dispatches customer and admin notifications.
    """
    user_id = str(current_user["id"]) if current_user and "id" in current_user else None
    reason = req.reason if req else "Change of plans"
    comments = req.comments if req else None

    async with conn.transaction():
        booking = await _fetch_booking_for_cancellation(
            booking_id, user_id, conn, for_update=True
        )

        policy = await get_show_cancellation_policy(conn, str(booking.get("show_id", "")))
        eligible, eval_reason, breakdown = evaluate_cancellation_eligibility(booking, policy)
        if not eligible:
            raise HTTPException(status_code=400, detail=eval_reason)

        # Seats a friend has accepted belong to them now; don't refund them to the booker.
        if await has_accepted_transfers(conn, booking_id):
            raise HTTPException(
                status_code=400,
                detail="Some seats on this booking were transferred to someone else, so it can't be cancelled.",
            )
        await close_pending_for_booking(conn, booking_id)

        refund_amount = float(breakdown.get("expected_refund", 0.0))
        cancellation_charge = float(breakdown.get("cancellation_charge", 0.0))
        has_payment = breakdown.get("has_payment", False)
        initial_refund_status = "PENDING" if (has_payment and refund_amount > 0) else "NOT_APPLICABLE"

        # Update Booking Status
        await conn.execute(
            """
            UPDATE bookings
            SET status = 'cancelled',
                cancellation_reason = $1,
                cancellation_notes = $2,
                cancellation_charge = $3,
                refund_amount = $4,
                refund_status = $5,
                cancelled_at = now(),
                updated_at = now()
            WHERE id = $6::uuid
            """,
            reason,
            comments,
            cancellation_charge,
            refund_amount,
            initial_refund_status,
            booking_id,
        )

        # Cancel Associated Ticket
        await conn.execute(
            "UPDATE tickets SET status = 'cancelled' WHERE booking_id = $1::uuid",
            booking_id,
        )

        # Safely release seats exactly once
        await conn.execute(
            """
            UPDATE show_seats
            SET status = 'available', locked_by = NULL, locked_until = NULL
            WHERE id IN (
                SELECT show_seat_id FROM booking_seats WHERE booking_id = $1::uuid
            )
            """,
            booking_id,
        )

        # Create Refund Record if paid
        refund_id_db = None
        if has_payment and refund_amount > 0 and booking.get("payment_id"):
            try:
                import inspect
                if hasattr(conn, "fetchval"):
                    res = conn.fetchval(
                        """
                        INSERT INTO refunds (
                            booking_id, payment_id, user_id, amount, cancellation_charge,
                            currency, status, razorpay_payment_id, policy_snapshot
                        )
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 'INR', 'PENDING', $6, $7::jsonb)
                        RETURNING id::text
                        """,
                        booking_id,
                        booking["payment_id"],
                        user_id,
                        refund_amount,
                        cancellation_charge,
                        booking.get("transaction_id"),
                        json.dumps(policy),
                    )
                    if inspect.isawaitable(res):
                        refund_id_db = await res
            except Exception:
                pass

    # Outside atomic commit: Call Payment Gateway
    gateway_refund_id = None
    gateway_status = initial_refund_status
    has_transaction = has_payment and refund_amount > 0 and bool(booking.get("transaction_id"))

    if has_transaction:
        amount_paise = round(refund_amount * 100)
        if background_tasks is not None:
            background_tasks.add_task(
                refund_and_record,
                str(booking["payment_id"]),
                booking["transaction_id"],
                amount_paise,
            )
            gateway_status = "PROCESSED"
        else:
            try:
                rz_res = await initiate_razorpay_refund(
                    booking["transaction_id"],
                    amount_paise,
                    notes={"booking_id": booking_id, "refund_id": refund_id_db or ""},
                )
                gateway_refund_id = rz_res if isinstance(rz_res, str) else (rz_res.get("id") or rz_res.get("refund_id"))
                raw_status = (rz_res.get("status") or "PENDING").upper() if isinstance(rz_res, dict) else "PROCESSED"
                if raw_status in ("PROCESSED", "REFUNDED") or isinstance(rz_res, str):
                    gateway_status = "PROCESSED"
                elif raw_status == "FAILED" or (isinstance(rz_res, dict) and rz_res.get("error")):
                    gateway_status = "FAILED"
                else:
                    gateway_status = "PENDING"

                if gateway_status == "PROCESSED":
                    await conn.execute(
                        """
                        UPDATE refunds
                        SET razorpay_refund_id = $1, status = 'PROCESSED', updated_at = now(), completed_at = now()
                        WHERE id = $2::uuid
                        """,
                        gateway_refund_id,
                        refund_id_db,
                    )
                    await conn.execute(
                        """
                        UPDATE payments
                        SET status = 'refunded', razorpay_refund_id = $1,
                            refunded_amount = $2, refunded_at = now()
                        WHERE id = $3::uuid
                        """,
                        gateway_refund_id,
                        refund_amount,
                        booking["payment_id"],
                    )
                    await conn.execute(
                        "UPDATE bookings SET refund_status = 'REFUNDED' WHERE id = $1::uuid",
                        booking_id,
                    )
                elif gateway_status == "FAILED":
                    fail_err = (rz_res.get("error") if isinstance(rz_res, dict) else None) or "Gateway error"
                    await conn.execute(
                        """
                        UPDATE refunds
                        SET status = 'FAILED', failure_reason = $1, updated_at = now()
                        WHERE id = $2::uuid
                        """,
                        fail_err,
                        refund_id_db,
                    )
                    await conn.execute(
                        "UPDATE bookings SET refund_status = 'REFUND_FAILED' WHERE id = $1::uuid",
                        booking_id,
                    )
                    await notify_admins(
                        conn,
                        "refund.failed",
                        {
                            "booking_id": booking_id,
                            "refund_id": refund_id_db,
                            "amount": refund_amount,
                            "error": fail_err,
                            "customer_name": booking["user_name"],
                        },
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE refunds
                        SET razorpay_refund_id = $1, status = 'PENDING', updated_at = now()
                        WHERE id = $2::uuid
                        """,
                        gateway_refund_id,
                        refund_id_db,
                    )
                    await conn.execute(
                        "UPDATE bookings SET refund_status = 'PENDING' WHERE id = $1::uuid",
                        booking_id,
                    )
            except Exception as exc:
                gateway_status = "FAILED"
                print(f"[cancellation] Razorpay refund invocation failed: {exc}")
                if refund_id_db:
                    await conn.execute(
                        """
                        UPDATE refunds
                        SET status = 'FAILED', failure_reason = $1, updated_at = now()
                        WHERE id = $2::uuid
                        """,
                        str(exc),
                        refund_id_db,
                    )
                    await conn.execute(
                        "UPDATE bookings SET refund_status = 'REFUND_FAILED' WHERE id = $1::uuid",
                        booking_id,
                    )

                await notify_admins(
                    conn,
                    "refund.failed",
                    {
                        "booking_id": booking_id,
                        "refund_id": refund_id_db,
                        "amount": refund_amount,
                        "error": str(exc),
                        "customer_name": booking["user_name"],
                    },
                )

    # Notifications
    seats_list = [f"{s['row_label']}{s['seat_number']}" for s in booking.get("seats_info", [])]
    notif_payload = {
        "booking_id": booking_id,
        "event_title": booking.get("event_title", "Event"),
        "refund_amount": refund_amount,
        "cancellation_charge": cancellation_charge,
        "refund_status": gateway_status,
        "seats": seats_list,
    }

    if user_id:
        try:
            await create_notification(conn, user_id, "booking.cancelled", notif_payload)
            if gateway_status == "PROCESSED":
                await create_notification(conn, user_id, "refund.successful", notif_payload)
            elif gateway_status in ("PROCESSING", "PENDING"):
                await create_notification(conn, user_id, "refund.initiated", notif_payload)
        except Exception:
            pass

    # Customer Email
    if booking.get("user_email"):
        try:
            await send_cancellation_email(
                booking["user_email"],
                booking.get("user_name", "Customer"),
                booking_id,
                booking.get("event_title", "Event"),
                booking.get("venue_name", "Venue"),
                booking["start_time"].strftime("%a, %d %b %Y at %I:%M %p") if booking.get("start_time") else "",
                seats_list,
                refund_amount,
                cancellation_charge,
            )
        except Exception:
            pass

    msg = (
        f"Booking successfully cancelled. Refund of ₹{refund_amount:.2f} initiated."
        if refund_amount > 0 and gateway_status != "FAILED"
        else "Booking cancelled. No refundable payment on record."
        if refund_amount == 0
        else "Booking cancelled. Automatic gateway refund failed — support team alerted."
    )

    return {
        "status": "cancelled",
        "refund_initiated": has_transaction,
        "refund_status": gateway_status,
        "refund_amount": refund_amount,
        "cancellation_charge": cancellation_charge,
        "razorpay_refund_id": gateway_refund_id,
        "message": msg,
        "note": msg,
    }


@router.get("/{booking_id}/refund-status")
async def get_booking_refund_status(
    booking_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Returns refund timeline and tracking details for customer booking view.
    """
    booking = await _fetch_booking_for_cancellation(
        booking_id, str(current_user["id"]), conn
    )
    refund = None
    if hasattr(conn, "fetchrow") and callable(getattr(conn, "fetchrow", None)):
        try:
            import inspect
            res = conn.fetchrow(
                """
                SELECT id, amount, cancellation_charge, status, razorpay_payment_id,
                       razorpay_refund_id, failure_reason, retry_count, last_retried_at,
                       created_at, updated_at, completed_at
                FROM refunds
                WHERE booking_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT 1
                """,
                booking_id,
            )
            if inspect.isawaitable(res):
                refund_row = await res
                if refund_row:
                    refund = dict(refund_row)
        except Exception:
            pass

    return {
        "booking_id": booking_id,
        "booking_status": booking["status"],
        "refund_status": booking.get("refund_status") or (refund["status"] if refund else "NOT_APPLICABLE"),
        "total_amount": float(booking.get("total_amount", 0.0)),
        "cancellation_charge": float(booking.get("cancellation_charge", 0.0)),
        "refund_amount": float(booking.get("refund_amount", 0.0)),
        "cancelled_at": booking.get("cancelled_at").isoformat() if booking.get("cancelled_at") else None,
        "refund": refund,
    }


# ── Razorpay Webhook Endpoint ─────────────────────────────────────────────────

@router.post("/refund-webhook")
async def razorpay_refund_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Receives and processes verified Razorpay refund webhook events:
    - refund.processed
    - refund.failed
    """
    body = await request.body()

    if not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Razorpay webhook secret not configured on server")

    if not x_razorpay_signature or not verify_razorpay_webhook_signature(
        body, x_razorpay_signature, RAZORPAY_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = data.get("event")
    payload = data.get("payload", {}).get("refund", {}).get("entity", {})
    refund_id = payload.get("id")
    rz_payment_id = payload.get("payment_id")

    if not refund_id:
        return {"status": "ignored", "reason": "No refund entity found"}

    refund_row = await conn.fetchrow(
        """
        SELECT r.id, r.booking_id, r.user_id, r.amount, r.status,
               b.event_title, u.email AS user_email, u.name AS user_name
        FROM refunds r
        JOIN bookings b ON b.id = r.booking_id
        JOIN users u ON u.id = r.user_id
        WHERE r.razorpay_refund_id = $1 OR r.razorpay_payment_id = $2
        LIMIT 1
        """,
        refund_id,
        rz_payment_id,
    )

    if not refund_row:
        return {"status": "ignored", "reason": "Refund record not mapped"}

    db_refund_id = refund_row["id"]
    booking_id = refund_row["booking_id"]
    user_id = str(refund_row["user_id"])
    refund_amount = float(refund_row["amount"])

    if event == "refund.processed":
        await conn.execute(
            """
            UPDATE refunds
            SET status = 'PROCESSED', razorpay_refund_id = $1, completed_at = now(), updated_at = now()
            WHERE id = $2::uuid
            """,
            refund_id,
            db_refund_id,
        )
        await conn.execute(
            "UPDATE bookings SET refund_status = 'REFUNDED', updated_at = now() WHERE id = $1::uuid",
            booking_id,
        )
        await create_notification(
            conn,
            user_id,
            "refund.successful",
            {"booking_id": str(booking_id), "refund_amount": refund_amount, "reference": refund_id},
        )
        u_email = refund_row.get("user_email") or refund_row.get("customer_email") or ""
        u_name = refund_row.get("user_name") or refund_row.get("customer_name") or "Customer"
        await send_refund_status_email(
            u_email,
            u_name,
            str(booking_id),
            refund_row.get("event_title", "Event"),
            "processed",
            refund_amount,
            refund_id,
        )

    elif event == "refund.failed":
        reason = payload.get("error_description") or "Gateway processing error"
        await conn.execute(
            """
            UPDATE refunds
            SET status = 'FAILED', failure_reason = $1, razorpay_refund_id = $2, updated_at = now()
            WHERE id = $3::uuid
            """,
            reason,
            refund_id,
            db_refund_id,
        )
        await conn.execute(
            "UPDATE bookings SET refund_status = 'REFUND_FAILED', updated_at = now() WHERE id = $1::uuid",
            booking_id,
        )
        await create_notification(
            conn,
            user_id,
            "refund.failed",
            {"booking_id": str(booking_id), "refund_amount": refund_amount, "reason": reason},
        )
        await notify_admins(
            conn,
            "refund.failed",
            {"booking_id": str(booking_id), "refund_id": str(db_refund_id), "amount": refund_amount, "reason": reason},
        )
        u_email = refund_row.get("user_email") or refund_row.get("customer_email") or ""
        u_name = refund_row.get("user_name") or refund_row.get("customer_name") or "Customer"
        await send_refund_status_email(
            u_email,
            u_name,
            str(booking_id),
            refund_row.get("event_title", "Event"),
            "failed",
            refund_amount,
            refund_id,
            failure_reason=reason,
        )

    return {"status": "success", "event": event}


# ── Administrator Endpoints ───────────────────────────────────────────────────

@router.get("/admin/cancellations")
async def list_admin_cancellations(
    search: Optional[str] = None,
    refund_status: Optional[str] = None,
    current_admin: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Admin listing for all cancelled bookings and refund statuses with filtering.
    """
    conditions = ["b.status = 'cancelled'"]
    params = []

    if refund_status and refund_status != "all":
        params.append(refund_status.upper())
        conditions.append(f"UPPER(b.refund_status) = ${len(params)}")

    if search and search.strip():
        params.append(f"%{search.strip()}%")
        conditions.append(
            f"(b.id::text ILIKE ${len(params)} OR u.name ILIKE ${len(params)} OR u.email ILIKE ${len(params)} OR e.title ILIKE ${len(params)})"
        )

    where_sql = " AND ".join(conditions)

    rows = await conn.fetch(
        f"""
        SELECT b.id AS booking_id, b.total_amount, b.cancellation_charge,
               b.refund_amount, b.refund_status, b.cancellation_reason,
               b.cancellation_notes, b.cancelled_at,
               u.id AS user_id, u.name AS customer_name, u.email AS customer_email,
               e.title AS event_title, s.start_time,
               r.id AS refund_id, r.status AS detailed_refund_status,
               r.razorpay_refund_id, r.failure_reason, r.retry_count
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        JOIN shows s ON s.id = b.show_id
        JOIN events e ON e.id = s.event_id
        LEFT JOIN refunds r ON r.booking_id = b.id
        WHERE {where_sql}
        ORDER BY b.cancelled_at DESC NULLS LAST
        LIMIT 100
        """,
        *params,
    )

    return [dict(r) for r in rows]


@router.post("/admin/refunds/{refund_id}/retry")
async def retry_failed_refund(
    refund_id: str,
    req: RetryRefundRequest,
    current_admin: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Admin action to retry an eligible failed refund.
    Maintains audit logging of who initiated the retry.
    """
    refund = await conn.fetchrow(
        "SELECT * FROM refunds WHERE id = $1::uuid FOR UPDATE", refund_id
    )
    if not refund:
        raise HTTPException(status_code=404, detail="Refund record not found")

    if refund["status"] not in ("FAILED", "PENDING"):
        raise HTTPException(
            status_code=400,
            detail=f"Refund is already in status {refund['status']} and cannot be retried.",
        )

    amount_paise = round(float(refund["amount"]) * 100)
    rz_payment_id = refund["razorpay_payment_id"]
    admin_id = str(current_admin["id"])

    try:
        rz_res = await initiate_razorpay_refund(
            rz_payment_id,
            amount_paise,
            notes={"refund_id": refund_id, "retried_by": admin_id},
        )
        new_rz_refund_id = rz_res if isinstance(rz_res, str) else (rz_res.get("id") or rz_res.get("refund_id"))
        raw_status = (rz_res.get("status") or "PENDING").upper() if isinstance(rz_res, dict) else "PROCESSED"
        new_status = "PROCESSED" if (raw_status in ("PROCESSED", "REFUNDED") or isinstance(rz_res, str)) else "PROCESSING"

        await conn.execute(
            """
            UPDATE refunds
            SET status = $1, razorpay_refund_id = $2, failure_reason = NULL,
                retry_count = retry_count + 1, last_retried_at = now(),
                retried_by = $3::uuid, updated_at = now(),
                completed_at = CASE WHEN $1 = 'PROCESSED' THEN now() ELSE NULL END
            WHERE id = $4::uuid
            """,
            new_status,
            new_rz_refund_id,
            admin_id,
            refund_id,
        )

        await conn.execute(
            "UPDATE bookings SET refund_status = $1 WHERE id = $2::uuid",
            new_status,
            refund["booking_id"],
        )

        return {
            "status": "success",
            "refund_status": new_status,
            "razorpay_refund_id": new_rz_refund_id,
        }

    except Exception as exc:
        logger.exception("Refund retry failed for refund %s", refund_id)
        await conn.execute(
            """
            UPDATE refunds
            SET status = 'FAILED', failure_reason = $1,
                retry_count = retry_count + 1, last_retried_at = now(),
                retried_by = $2::uuid, updated_at = now()
            WHERE id = $3::uuid
            """,
            str(exc),
            admin_id,
            refund_id,
        )
        raise HTTPException(
            status_code=500,
            detail="The refund could not be retried. Please try again later or contact support.",
        )
