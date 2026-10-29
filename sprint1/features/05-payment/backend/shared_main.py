"""Shared Supabase/PostgreSQL Razorpay Test Mode integration for Feature 05.

This app uses the team's `bookings`, `booking_seats`, `show_seats`, `payments`,
`receipts`, and related tables. It authenticates Firebase ID tokens and never
trusts a client-supplied amount or internal user ID.
"""
from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT.parents[1] / ".env", override=False)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("PAYMENT_STORAGE=postgres requires DATABASE_URL in the server environment.")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
if DATABASE_URL.startswith("postgresql+psycopg2://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

engine_options: dict[str, Any] = {"pool_pre_ping": True}
if DATABASE_URL.startswith(("postgresql+psycopg://", "postgresql://")):
    engine_options.update({"pool_size": 5, "max_overflow": 5})
engine: Engine = create_engine(DATABASE_URL, **engine_options)

app = FastAPI(
    title="Cinepass Payment Gateway — Shared DB",
    version="3.0.0",
    description="Feature 05 API using the team Supabase/PostgreSQL schema and Razorpay Test Mode.",
)

allowed_origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def no_store(request: Request, call_next):
    request.scope["headers"] = [
        (name, value) for name, value in request.scope.get("headers", [])
        if name.lower() not in {b"if-none-match", b"if-modified-since"}
    ]
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def active_provider() -> str:
    provider = os.getenv("PAYMENT_PROVIDER", "razorpay").strip().lower()
    if provider != "razorpay":
        raise HTTPException(status_code=503, detail="Shared database mode supports Razorpay Test Mode only.")
    return provider


def get_razorpay_client():
    active_provider()
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        raise HTTPException(status_code=503, detail="Razorpay Test Mode is not configured on the server.")
    if not key_id.startswith("rzp_test_"):
        raise HTTPException(status_code=503, detail="Only Razorpay Test Mode keys are permitted by this feature.")
    try:
        import razorpay
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Razorpay SDK is unavailable; reinstall backend requirements.") from exc
    return razorpay.Client(auth=(key_id, key_secret))


def firebase_auth_module():
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Firebase Admin SDK is not installed on the backend.") from exc
    try:
        firebase_admin.get_app()
    except ValueError:
        credential_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "").strip()
        try:
            if credential_path:
                firebase_admin.initialize_app(credentials.Certificate(credential_path))
            else:
                # Supports GOOGLE_APPLICATION_CREDENTIALS / cloud workload identity.
                firebase_admin.initialize_app()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Firebase Admin credentials are not configured on this server.") from exc
    return auth


def current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    auth = firebase_auth_module()
    try:
        decoded = auth.verify_id_token(token, check_revoked=True)
        firebase_uid = str(decoded.get("uid") or "")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Sign in again.") from exc
    if not firebase_uid:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Sign in again.")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id::text AS id FROM users WHERE firebase_uid=:uid AND status::text='active'"), {"uid": firebase_uid}).mappings().first()
    if not row:
        raise HTTPException(status_code=403, detail="Your account is not registered or is inactive in the booking system.")
    return {"id": str(row["id"]), "firebase_uid": firebase_uid}


def money(value: Decimal | int | float | str) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"₹{amount:,.2f}"


def amount_to_paise(value: Decimal | int | float | str) -> int:
    return int((Decimal(str(value)) * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def provider_created_at(provider_payment: dict) -> datetime | None:
    value = provider_payment.get("created_at")
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(value), timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def get_booking_row(conn, booking_id: str, user_id: str, *, for_update: bool = False):
    suffix = " FOR UPDATE OF b" if for_update else ""
    return conn.execute(text(f"""
        SELECT b.id::text AS booking_id, b.booking_number, b.user_id::text AS user_id,
               b.show_id::text AS show_id, b.total_amount, b.currency,
               b.status::text AS status, b.booked_at,
               e.title AS event_title, e.event_type::text AS event_type, e.poster_url,
               sh.start_time, sh.end_time, sc.name AS screen_name,
               v.name AS venue, v.city
        FROM bookings b
        JOIN shows sh ON sh.id=b.show_id
        JOIN events e ON e.id=sh.event_id
        JOIN screens sc ON sc.id=sh.screen_id
        JOIN venues v ON v.id=sc.venue_id
        WHERE b.id=CAST(:booking_id AS uuid) AND b.user_id=CAST(:user_id AS uuid)
        {suffix}
    """), {"booking_id": booking_id, "user_id": user_id}).mappings().first()


def booking_payload(conn, booking_id: str, user_id: str, *, for_update: bool = False) -> dict:
    row = get_booking_row(conn, booking_id, user_id, for_update=for_update)
    if not row:
        # Deliberately do not reveal whether a booking exists for another user.
        raise HTTPException(status_code=404, detail="Booking was not found.")
    seat_lock_clause = " FOR UPDATE OF ss" if for_update else ""
    seats = conn.execute(text(f"""
        SELECT s.row_label || s.seat_number::text AS seat_label,
               ss.price, ss.status::text AS seat_status,
               ss.locked_until, ss.locked_by::text AS locked_by,
               ss.id::text AS show_seat_id
        FROM booking_seats bs
        JOIN show_seats ss ON ss.id=bs.show_seat_id
        JOIN seats s ON s.id=ss.seat_id
        WHERE bs.booking_id=CAST(:booking_id AS uuid)
        ORDER BY s.row_label, s.seat_number{seat_lock_clause}
    """), {"booking_id": booking_id}).mappings().all()
    start_time = row["start_time"]
    total = Decimal(str(row["total_amount"]))
    lock_count = sum(
        1 for seat in seats
        if seat["seat_status"] == "locked"
        and seat["locked_by"] == row["user_id"]
        and seat["locked_until"] is not None
        and seat["locked_until"] > datetime.now(timezone.utc)
    )
    # Only the persisted booking total is available in the team's schema. Do not
    # invent a fee/tax breakdown for the payment UI.
    return {
        "booking_id": str(row["booking_id"]),
        "booking_number": row["booking_number"],
        "event_title": row["event_title"],
        "event_type": row["event_type"],
        "poster_url": row["poster_url"],
        "venue": row["venue"],
        "screen": row["screen_name"],
        "city": row["city"],
        "show_date": iso(start_time),
        "show_time": start_time.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%H:%M IST") if start_time and start_time.tzinfo else start_time.strftime("%H:%M") if start_time else None,
        "seats": [str(seat["seat_label"]) for seat in seats],
        "ticket_count": len(seats),
        "currency": row["currency"],
        "total_amount_decimal": str(total),
        "total_paise": amount_to_paise(total),
        "total": money(total),
        "subtotal": money(total),
        "convenience_fee": None,
        "tax": None,
        "price_breakdown_available": False,
        "status": row["status"],
        "seat_locks_valid": bool(seats) and lock_count == len(seats),
    }


def order_row_for_user(conn, order_id: str, user_id: str, *, for_update: bool = False):
    suffix = " FOR UPDATE OF po" if for_update else ""
    return conn.execute(text(f"""
        SELECT po.id::text AS id, po.booking_id::text AS booking_id,
               po.razorpay_order_id AS order_id, po.amount, po.currency,
               po.status, po.created_at, po.updated_at, po.created_by::text AS created_by,
               b.user_id::text AS user_id, b.status::text AS booking_status
        FROM payment_orders po JOIN bookings b ON b.id=po.booking_id
        WHERE po.razorpay_order_id=:order_id AND b.user_id=CAST(:user_id AS uuid)
        {suffix}
    """), {"order_id": order_id, "user_id": user_id}).mappings().first()


def payment_result(conn, order_id: str, user_id: str) -> dict:
    order = order_row_for_user(conn, order_id, user_id)
    if not order:
        raise HTTPException(status_code=404, detail="Payment order was not found.")
    booking = booking_payload(conn, order["booking_id"], user_id)
    payment = conn.execute(text("""
        SELECT p.id::text AS id, p.razorpay_payment_id, p.status::text AS status,
               p.provider_method, p.paid_at, p.provider_created_at, p.failure_reason,
               r.receipt_number, r.issued_at AS receipt_issued_at
        FROM payments p
        LEFT JOIN receipts r ON r.payment_id=p.id
        WHERE p.payment_order_id=CAST(:payment_order_id AS uuid)
        ORDER BY p.created_at DESC LIMIT 1
    """), {"payment_order_id": order["id"]}).mappings().first()
    amount_paise = amount_to_paise(order["amount"])
    payment_status = None
    if payment:
        if order["status"] == "authorized":
            payment_status = "authorized"
        elif order["status"] == "verification_pending":
            payment_status = "verification_pending"
        else:
            payment_status = payment["status"]
    receipt = None
    if payment and payment["receipt_number"]:
        receipt = {"receipt_number": payment["receipt_number"], "issued_at": iso(payment["receipt_issued_at"])}
    result = {
        "order_id": order["order_id"],
        "booking_id": order["booking_id"],
        "amount_paise": amount_paise,
        "amount": money(order["amount"]),
        "currency": order["currency"],
        "method": payment["provider_method"] if payment and payment["provider_method"] else "Not available yet",
        "status": order["status"],
        "created_at": iso(order["created_at"]),
        "booking": booking,
        "payment": None if not payment else {
            "payment_id": payment["razorpay_payment_id"],
            "status": payment_status or payment["status"],
            "outcome": order["status"],
            "paid_at": iso(payment["paid_at"]),
            "created_at": iso(payment["provider_created_at"] or payment["paid_at"]),
            "method": payment["provider_method"],
            "failure_reason": payment["failure_reason"],
        },
        "receipt": receipt,
        "provider": "razorpay",
        "sandbox": True,
        "live_payment": False,
        "booking_confirmation_status": "confirmed" if booking["status"] == "confirmed" else ("needs_attention" if order["status"] == "successful_needs_review" else "pending"),
        "message": "Razorpay Test Mode — no live money was charged.",
        "key_id": os.getenv("RAZORPAY_KEY_ID", "").strip(),
    }
    return result


class CreateOrderRequest(BaseModel):
    booking_id: str = Field(min_length=1, max_length=100)


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=500)


class RecheckPaymentRequest(BaseModel):
    payment_id: str | None = Field(default=None, min_length=1, max_length=100)


def provider_payment_with_retries(client, payment_id: str, attempts: int = 3) -> dict:
    last_error = None
    for attempt in range(attempts):
        try:
            return client.payment.fetch(payment_id)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.35 * (2 ** attempt))
    raise RuntimeError("Could not fetch payment status") from last_error


def provider_order_payments_with_retries(client, order_id: str, attempts: int = 3) -> dict:
    last_error = None
    for attempt in range(attempts):
        try:
            return client.order.payments(order_id)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.35 * (2 ** attempt))
    raise RuntimeError("Could not fetch payment attempts") from last_error


def provider_order_with_retries(client, order_id: str, attempts: int = 3) -> dict:
    last_error = None
    for attempt in range(attempts):
        try:
            return client.order.fetch(order_id)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.35 * (2 ** attempt))
    raise RuntimeError("Could not fetch order status") from last_error


def select_provider_payment(items: list[dict], order_id: str) -> dict | None:
    candidates = [x for x in items if isinstance(x, dict) and x.get("id") and x.get("order_id") == order_id]
    candidates.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
    return (next((x for x in candidates if x.get("status") == "captured"), None)
            or next((x for x in candidates if x.get("status") == "authorized"), None)
            or (candidates[0] if candidates else None))


def _seat_rows_for_confirmation(conn, booking_id: str):
    return conn.execute(text("""
        SELECT ss.id::text AS id, ss.status::text AS status,
               ss.locked_until, ss.locked_by::text AS locked_by
        FROM booking_seats bs JOIN show_seats ss ON ss.id=bs.show_seat_id
        WHERE bs.booking_id=CAST(:booking_id AS uuid)
        ORDER BY ss.id FOR UPDATE OF ss
    """), {"booking_id": booking_id}).mappings().all()


def record_provider_state(order_id: str, user_id: str, provider_payment: dict, signature_verified: bool) -> dict:
    order_key = str(provider_payment.get("order_id") or "")
    payment_id = str(provider_payment.get("id") or "")
    if not payment_id:
        raise HTTPException(status_code=502, detail="Razorpay did not return a payment reference.")
    provider_status = str(provider_payment.get("status", "unknown")).lower()
    provider_method = str(provider_payment.get("method") or "").lower() or None
    provider_time = provider_created_at(provider_payment)

    with engine.begin() as conn:
        order = order_row_for_user(conn, order_id, user_id, for_update=True)
        if not order:
            raise HTTPException(status_code=404, detail="Payment order was not found.")
        if order_key != order_id:
            raise HTTPException(status_code=400, detail="Razorpay payment does not belong to this order.")
        if int(provider_payment.get("amount", -1)) != amount_to_paise(order["amount"]):
            raise HTTPException(status_code=400, detail="Razorpay payment amount does not match this booking.")
        if str(provider_payment.get("currency", "")) != order["currency"]:
            raise HTTPException(status_code=400, detail="Razorpay payment currency does not match this booking.")

        local_status = "successful" if provider_status == "captured" else ("failed" if provider_status == "failed" else "pending")
        now = datetime.now(timezone.utc)
        existing = conn.execute(text("SELECT id::text AS id, payment_order_id::text AS payment_order_id, status::text AS status FROM payments WHERE razorpay_payment_id=:pid FOR UPDATE"), {"pid": payment_id}).mappings().first()
        if existing and existing["payment_order_id"] != order["id"]:
            raise HTTPException(status_code=409, detail="This payment reference is already linked to another order.")
        if existing and existing["status"] == "successful":
            return payment_result(conn, order_id, user_id)

        failure_reason = None
        if provider_status == "failed":
            error = provider_payment.get("error_description") or provider_payment.get("error_reason") or provider_payment.get("error_code")
            failure_reason = str(error)[:500] if error else "Razorpay reported a failed payment attempt."

        values = {
            "booking_id": order["booking_id"], "transaction_id": payment_id,
            "amount": Decimal(str(order["amount"])), "currency": order["currency"],
            "payment_status": local_status, "provider_method": provider_method,
            "pid": payment_id, "payment_order_id": order["id"],
            "provider_created_at": provider_time, "paid_at": now if provider_status == "captured" else None,
            "signature_verified_at": now if signature_verified else None,
            "failure_reason": failure_reason,
        }
        if existing:
            conn.execute(text("""
                UPDATE payments SET status=CAST(:payment_status AS payment_status),
                    transaction_id=:transaction_id, amount=:amount, currency=:currency,
                    provider_method=:provider_method, provider_created_at=COALESCE(:provider_created_at, provider_created_at),
                    paid_at=COALESCE(:paid_at, paid_at), signature_verified_at=COALESCE(:signature_verified_at, signature_verified_at),
                    failure_reason=:failure_reason
                WHERE id=CAST(:payment_row_id AS uuid)
            """), {**values, "payment_row_id": existing["id"]})
            payment_row_id = existing["id"]
        else:
            inserted = conn.execute(text("""
                INSERT INTO payments (booking_id, transaction_id, amount, currency, payment_method, status,
                    paid_at, payment_order_id, razorpay_payment_id, provider_method, provider_created_at,
                    signature_verified_at, failure_reason)
                VALUES (CAST(:booking_id AS uuid), :transaction_id, :amount, :currency,
                    'razorpay'::payment_method, CAST(:payment_status AS payment_status), :paid_at,
                    CAST(:payment_order_id AS uuid), :pid, :provider_method, :provider_created_at,
                    :signature_verified_at, :failure_reason)
                RETURNING id::text AS id
            """), values).mappings().one()
            payment_row_id = inserted["id"]

        if provider_status == "captured":
            # Capture proves the money was collected, but the booking can only be
            # confirmed if the booking's own seat locks are still valid and owned.
            seat_rows = _seat_rows_for_confirmation(conn, order["booking_id"])
            valid = bool(seat_rows) and all(
                s["status"] == "locked" and s["locked_by"] == order["user_id"]
                and s["locked_until"] is not None and s["locked_until"] > now
                for s in seat_rows
            )
            if valid:
                conn.execute(text("""
                    UPDATE show_seats ss SET status='booked', locked_until=NULL, locked_by=NULL
                    WHERE ss.id IN (SELECT show_seat_id FROM booking_seats WHERE booking_id=CAST(:booking_id AS uuid))
                      AND ss.status='locked' AND ss.locked_by=CAST(:user_id AS uuid)
                """), {"booking_id": order["booking_id"], "user_id": order["user_id"]})
                conn.execute(text("UPDATE bookings SET status='confirmed', booked_at=COALESCE(booked_at, :now), updated_at=:now WHERE id=CAST(:booking_id AS uuid)"), {"booking_id": order["booking_id"], "now": now})
                final_order_status = "successful"
            else:
                # Do not double-book seats if locks expired or were reassigned after
                # the customer paid. Keep this order blocking new attempts for review.
                final_order_status = "successful_needs_review"
            conn.execute(text("UPDATE payment_orders SET status=:status, updated_at=:now WHERE id=CAST(:id AS uuid)"), {"status": final_order_status, "now": now, "id": order["id"]})
            conn.execute(text("""
                INSERT INTO receipts(receipt_number, payment_id, issued_at)
                VALUES (:receipt, CAST(:payment_id AS uuid), :now)
                ON CONFLICT (payment_id) DO NOTHING
            """), {"receipt": "RCT-RZP-" + secrets.token_hex(5).upper(), "payment_id": payment_row_id, "now": now})
        elif provider_status == "failed":
            conn.execute(text("UPDATE payment_orders SET status='failed', updated_at=:now WHERE id=CAST(:id AS uuid)"), {"now": now, "id": order["id"]})
        elif provider_status == "authorized":
            conn.execute(text("UPDATE payment_orders SET status='authorized', updated_at=:now WHERE id=CAST(:id AS uuid)"), {"now": now, "id": order["id"]})
        else:
            conn.execute(text("UPDATE payment_orders SET status='verification_pending', updated_at=:now WHERE id=CAST(:id AS uuid)"), {"now": now, "id": order["id"]})
    with engine.connect() as conn:
        return payment_result(conn, order_id, user_id)


def reconcile_provider_payment(order_id: str, user_id: str, payment_id: str, client, signature_verified: bool = False) -> dict:
    try:
        provider_payment = provider_payment_with_retries(client, payment_id)
    except Exception:
        with engine.begin() as conn:
            order = order_row_for_user(conn, order_id, user_id, for_update=True)
            if not order:
                raise HTTPException(status_code=404, detail="Payment order was not found.")
            conn.execute(text("UPDATE payment_orders SET status='verification_pending', updated_at=now() WHERE id=CAST(:id AS uuid)"), {"id": order["id"]})
            if conn.execute(text("SELECT 1 FROM payments WHERE payment_order_id=CAST(:id AS uuid)"), {"id": order["id"]}).first():
                conn.execute(text("UPDATE payments SET status='pending'::payment_status WHERE payment_order_id=CAST(:id AS uuid) AND status IN ('created','pending')"), {"id": order["id"]})
        with engine.connect() as conn:
            return payment_result(conn, order_id, user_id)

    state = str(provider_payment.get("status", "unknown")).lower()
    if state == "authorized":
        try:
            captured = client.payment.capture(payment_id, {"amount": int(provider_payment.get("amount", 0)), "currency": provider_payment.get("currency", "INR")})
            if str(captured.get("status", "")).lower() == "captured":
                provider_payment = captured
            else:
                provider_payment = provider_payment_with_retries(client, payment_id)
        except Exception:
            try:
                provider_payment = provider_payment_with_retries(client, payment_id)
            except Exception:
                # Persist authorized/pending, never claim failure or invite another payment.
                provider_payment = {**provider_payment, "status": "authorized"}
    return record_provider_state(order_id, user_id, provider_payment, signature_verified)


@app.get("/")
def index():
    return {
        "service": "Cinepass Feature 05 — Razorpay Test Mode",
        "mode": "shared-postgresql",
        "frontend": "Import frontend/components/payment/PaymentCheckout.jsx into the team's React/Next.js app.",
        "docs": "/docs",
    }


@app.get("/api/health")
def health() -> dict:
    configured = bool(os.getenv("RAZORPAY_KEY_ID", "").strip().startswith("rzp_test_") and os.getenv("RAZORPAY_KEY_SECRET", "").strip())
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="The shared database is not reachable from the payment backend.") from exc
    return {"status": "ok", "provider": "razorpay", "mode": "test", "credentials_configured": configured,
            "storage": "supabase-postgresql", "database_connected": True, "live_payments": False}


@app.get("/api/payments/booking/{booking_id}")
def read_booking(booking_id: str, user: dict = Depends(current_user)) -> dict:
    with engine.connect() as conn:
        booking = booking_payload(conn, booking_id, user["id"])
        latest = conn.execute(text("""
            SELECT po.razorpay_order_id FROM payment_orders po
            WHERE po.booking_id=CAST(:booking_id AS uuid)
            ORDER BY po.created_at DESC LIMIT 1
        """), {"booking_id": booking_id}).first()
        if latest:
            try:
                booking["latest_payment"] = payment_result(conn, latest[0], user["id"])
            except HTTPException:
                pass
        return booking


@app.post("/api/payments/orders")
def create_order(payload: CreateOrderRequest, request: Request, user: dict = Depends(current_user)) -> dict:
    client = get_razorpay_client()
    with engine.begin() as conn:
        booking_row = get_booking_row(conn, payload.booking_id, user["id"], for_update=True)
        if not booking_row:
            raise HTTPException(status_code=404, detail="Booking was not found.")
        if booking_row["status"] == "confirmed":
            raise HTTPException(status_code=409, detail="This booking has already been paid.")
        if booking_row["status"] != "pending":
            raise HTTPException(status_code=409, detail="This booking is not awaiting payment.")
        booking = booking_payload(conn, payload.booking_id, user["id"], for_update=True)
        if not booking["seat_locks_valid"]:
            raise HTTPException(status_code=409, detail="Your selected seats are no longer locked for this booking. Return to seat selection and refresh availability before paying.")
        unresolved = conn.execute(text("""
            SELECT razorpay_order_id FROM payment_orders
            WHERE booking_id=CAST(:booking_id AS uuid)
              AND status IN ('creating','created','verification_pending','authorized','successful_needs_review')
            ORDER BY created_at DESC LIMIT 1
        """), {"booking_id": payload.booking_id}).first()
        if unresolved:
            raise HTTPException(status_code=409, detail=f"An existing payment order needs reconciliation: {unresolved[0]}. Check that same order before starting another payment.")

        if booking_row["currency"] != "INR":
            raise HTTPException(status_code=400, detail="This checkout currently supports INR bookings only.")
        total_amount = Decimal(str(booking_row["total_amount"]))
        amount_paise = amount_to_paise(total_amount)
        if amount_paise <= 0:
            raise HTTPException(status_code=400, detail="The booking total must be greater than zero.")
        try:
            remote = client.order.create(data={
                "amount": amount_paise,
                "currency": booking_row["currency"],
                "receipt": "CP" + secrets.token_hex(12),
                "notes": {"booking_id": payload.booking_id, "booking_number": booking_row["booking_number"]},
            })
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Razorpay could not create the order. Please retry after checking the provider status.") from exc
        remote_order_id = str(remote.get("id") or "")
        if not remote_order_id or int(remote.get("amount", -1)) != amount_paise or remote.get("currency") != booking_row["currency"]:
            raise HTTPException(status_code=502, detail="Razorpay returned an order that did not match the booking total.")
        inserted = conn.execute(text("""
            INSERT INTO payment_orders(booking_id, razorpay_order_id, amount, currency, status, created_by)
            VALUES (CAST(:booking_id AS uuid), :order_id, :amount, :currency, 'created', CAST(:user_id AS uuid))
            RETURNING id::text AS id
        """), {"booking_id": payload.booking_id, "order_id": remote_order_id, "amount": total_amount,
              "currency": booking_row["currency"], "user_id": user["id"]}).mappings().one()
    with engine.connect() as conn:
        return payment_result(conn, remote_order_id, user["id"])


@app.get("/api/payments/orders/{order_id}")
def read_payment_order(order_id: str, user: dict = Depends(current_user)) -> dict:
    with engine.connect() as conn:
        return payment_result(conn, order_id, user["id"])


@app.post("/api/payments/orders/{order_id}/verify")
def verify_payment(order_id: str, payload: VerifyPaymentRequest, user: dict = Depends(current_user)) -> dict:
    client = get_razorpay_client()
    if payload.razorpay_order_id != order_id:
        raise HTTPException(status_code=400, detail="The payment order ID does not match this checkout.")
    with engine.connect() as conn:
        order = order_row_for_user(conn, order_id, user["id"])
    if not order:
        raise HTTPException(status_code=404, detail="Payment order was not found.")
    if order["status"] in {"successful", "successful_needs_review", "failed", "cancelled"}:
        with engine.connect() as conn:
            return payment_result(conn, order_id, user["id"])
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Razorpay payment signature verification failed. The booking was not confirmed.") from exc
    # Persist the payment reference as pending before provider fetch, so the
    # same Payment ID can be reconciled if the network becomes unavailable.
    with engine.begin() as conn:
        order_locked = order_row_for_user(conn, order_id, user["id"], for_update=True)
        if not order_locked:
            raise HTTPException(status_code=404, detail="Payment order was not found.")
        exists = conn.execute(text("SELECT id FROM payments WHERE razorpay_payment_id=:pid"), {"pid": payload.razorpay_payment_id}).first()
        if not exists:
            conn.execute(text("""
                INSERT INTO payments(booking_id, transaction_id, amount, currency, payment_method, status,
                    payment_order_id, razorpay_payment_id, signature_verified_at)
                VALUES (CAST(:booking_id AS uuid), :pid, :amount, :currency, 'razorpay'::payment_method,
                    'pending'::payment_status, CAST(:payment_order_id AS uuid), :pid, now())
            """), {"booking_id": order_locked["booking_id"], "pid": payload.razorpay_payment_id,
                  "amount": order_locked["amount"], "currency": order_locked["currency"], "payment_order_id": order_locked["id"]})
        conn.execute(text("UPDATE payment_orders SET status='verification_pending', updated_at=now() WHERE id=CAST(:id AS uuid)"), {"id": order_locked["id"]})
    return reconcile_provider_payment(order_id, user["id"], payload.razorpay_payment_id, client, signature_verified=True)


@app.post("/api/payments/orders/{order_id}/recheck")
def recheck_payment(order_id: str, payload: RecheckPaymentRequest, user: dict = Depends(current_user)) -> dict:
    client = get_razorpay_client()
    with engine.connect() as conn:
        order = order_row_for_user(conn, order_id, user["id"])
        if not order:
            raise HTTPException(status_code=404, detail="Payment order was not found.")
        if order["status"] in {"successful", "successful_needs_review", "failed", "cancelled"}:
            result = payment_result(conn, order_id, user["id"])
            if order["status"] == "cancelled":
                result["no_payment_attempt"] = True
            return result
        existing = conn.execute(text("""
            SELECT razorpay_payment_id, status::text AS status
            FROM payments WHERE payment_order_id=CAST(:payment_order_id AS uuid)
            ORDER BY created_at DESC LIMIT 1
        """), {"payment_order_id": order["id"]}).mappings().first()
    payment_id = str((existing["razorpay_payment_id"] if existing else None) or payload.payment_id or "")
    if existing and payload.payment_id and existing["razorpay_payment_id"] and payload.payment_id != existing["razorpay_payment_id"]:
        raise HTTPException(status_code=409, detail="Payment ID does not match the payment linked to this order.")
    if payment_id:
        return reconcile_provider_payment(order_id, user["id"], payment_id, client)

    try:
        collection = provider_order_payments_with_retries(client, order_id)
    except Exception:
        with engine.begin() as conn:
            conn.execute(text("UPDATE payment_orders SET status='verification_pending', updated_at=now() WHERE razorpay_order_id=:oid"), {"oid": order_id})
        with engine.connect() as conn:
            return payment_result(conn, order_id, user["id"])
    items = collection.get("items") if isinstance(collection, dict) else None
    if not isinstance(items, list):
        with engine.connect() as conn:
            return payment_result(conn, order_id, user["id"])
    candidate = select_provider_payment(items, order_id)
    if candidate:
        return reconcile_provider_payment(order_id, user["id"], str(candidate["id"]), client)
    try:
        remote_order = provider_order_with_retries(client, order_id)
        no_attempt = int(remote_order.get("attempts", -1)) == 0 and int(remote_order.get("amount_paid", -1)) == 0 and str(remote_order.get("status", "")).lower() == "created"
    except Exception:
        no_attempt = False
    if no_attempt:
        with engine.begin() as conn:
            conn.execute(text("UPDATE payment_orders SET status='cancelled', updated_at=now() WHERE razorpay_order_id=:oid"), {"oid": order_id})
        with engine.connect() as conn:
            result = payment_result(conn, order_id, user["id"])
            result["no_payment_attempt"] = True
            return result
    with engine.begin() as conn:
        conn.execute(text("UPDATE payment_orders SET status='verification_pending', updated_at=now() WHERE razorpay_order_id=:oid"), {"oid": order_id})
    with engine.connect() as conn:
        return payment_result(conn, order_id, user["id"])


@app.get("/api/payments/receipts/{receipt_number}")
def read_receipt(receipt_number: str, user: dict = Depends(current_user)) -> dict:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT r.receipt_number, r.issued_at, p.razorpay_payment_id, p.paid_at,
                   p.amount, p.currency, p.status::text AS payment_status, p.provider_method,
                   po.razorpay_order_id, po.booking_id::text AS booking_id
            FROM receipts r JOIN payments p ON p.id=r.payment_id
            JOIN payment_orders po ON po.id=p.payment_order_id
            JOIN bookings b ON b.id=po.booking_id
            WHERE r.receipt_number=:receipt AND b.user_id=CAST(:user_id AS uuid)
        """), {"receipt": receipt_number, "user_id": user["id"]}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Receipt was not found.")
        return {
            "receipt_number": row["receipt_number"], "issued_at": iso(row["issued_at"]),
            "payment_id": row["razorpay_payment_id"], "order_id": row["razorpay_order_id"],
            "booking_id": row["booking_id"], "amount": money(row["amount"]), "currency": row["currency"],
            "status": row["payment_status"], "payment_method": row["provider_method"],
            "timestamp": iso(row["paid_at"] or row["issued_at"]), "provider": "razorpay",
            "sandbox": True, "live_payment": False,
        }
