"""Cinepass payment checkout with a local mock and Razorpay Test Mode provider.

The Razorpay Key Secret is read from the server-only .env file and is never
returned to the browser. Razorpay mode is locked to rzp_test_ keys; live keys
are deliberately rejected by this student-project integration.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
# Also accept the shared Sprint 1 env file so this feature can use the team's
# existing environment setup without copying secrets into source files.
load_dotenv(ROOT.parents[1] / ".env", override=False)
FRONTEND_DIR = ROOT / "frontend" / "standalone-preview"
DB_PATH = Path(os.getenv("PAYMENT_SANDBOX_DB", str(Path(__file__).resolve().parent / "sandbox.sqlite3")))

DEMO_BOOKINGS = [
    {
        "booking_id": "demo-booking-001",
        "booking_number": "CIN-260011",
        "event_title": "Sonic The Hedgehog 2",
        "event_type": "MOVIE",
        "venue": "PVR Acropolis",
        "screen": "Screen 2",
        "city": "Ahmedabad",
        "show_date": "Tue, 27 Oct 2026",
        "show_time": "18:35",
        "seats": ["E5", "E6"],
        "ticket_count": 2,
        "unit_price_paise": 32000,
        "convenience_fee_paise": 3000,
        "tax_paise": 540,
        "currency": "INR",
    }
]

app = FastAPI(
    title="Cinepass Payment Checkout",
    version="2.2.0",
    description="Cinema checkout with a local mock or Razorpay Test Mode integration.",
)


@app.middleware("http")
async def prevent_stale_checkout_cache(request: Request, call_next):
    """Disable conditional caching for the local checkout and its API.

    This keeps the browser from reusing stale HTML/JS and stops conditional
    static-file requests from returning 304 while the developer is iterating.
    A 304 is an HTTP cache response, never a payment status.
    """
    request.scope["headers"] = [
        (name, value)
        for name, value in request.scope.get("headers", [])
        if name.lower() not in {b"if-none-match", b"if-modified-since"}
    ]
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def active_provider() -> str:
    provider = os.getenv("PAYMENT_PROVIDER", "mock").strip().lower()
    if provider not in {"mock", "razorpay"}:
        raise HTTPException(status_code=500, detail="Payment provider configuration is invalid.")
    return provider


def get_razorpay_client():
    if active_provider() != "razorpay":
        raise HTTPException(status_code=400, detail="Secure payment is not available with the current configuration.")
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        raise HTTPException(status_code=503, detail="Secure payment is not configured on the server.")
    # Safety guard: this package is for Test Mode only and must not make live charges.
    if not key_id.startswith("rzp_test_"):
        raise HTTPException(status_code=503, detail="The configured payment key is not allowed in this environment.")
    try:
        import razorpay
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="The secure payment service is unavailable. Re-run ./run_local.sh to install requirements.") from exc
    return razorpay.Client(auth=(key_id, key_secret))


@contextmanager
def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def money(paise: int) -> str:
    return f"₹{paise / 100:,.2f}"


def booking_total(booking: dict) -> int:
    return int(booking["unit_price_paise"] * booking["ticket_count"] + booking["convenience_fee_paise"] + booking["tax_paise"])


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sandbox_bookings (
                booking_id TEXT PRIMARY KEY,
                booking_number TEXT NOT NULL,
                booking_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sandbox_orders (
                order_id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL REFERENCES sandbox_bookings(booking_id),
                amount_paise INTEGER NOT NULL CHECK(amount_paise >= 0),
                currency TEXT NOT NULL,
                method TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'mock'
            );
            CREATE TABLE IF NOT EXISTS sandbox_payments (
                payment_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL UNIQUE REFERENCES sandbox_orders(order_id),
                amount_paise INTEGER NOT NULL CHECK(amount_paise >= 0),
                currency TEXT NOT NULL,
                status TEXT NOT NULL,
                outcome TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                method TEXT,
                provider_created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sandbox_receipts (
                receipt_number TEXT PRIMARY KEY,
                payment_id TEXT NOT NULL UNIQUE REFERENCES sandbox_payments(payment_id),
                issued_at TEXT NOT NULL
            );
            """
        )
        # Migrate existing local sandbox DBs created by earlier versions.
        ensure_column(conn, "sandbox_orders", "provider", "TEXT NOT NULL DEFAULT 'mock'")
        ensure_column(conn, "sandbox_payments", "method", "TEXT")
        ensure_column(conn, "sandbox_payments", "provider_created_at", "TEXT")
        for booking in DEMO_BOOKINGS:
            conn.execute(
                "INSERT OR IGNORE INTO sandbox_bookings(booking_id, booking_number, booking_json, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
                (booking["booking_id"], booking["booking_number"], json.dumps(booking), now_iso()),
            )


@app.on_event("startup")
def startup() -> None:
    init_db()


class CreateOrderRequest(BaseModel):
    booking_id: str = Field(min_length=1, max_length=100)
    # Deliberately no method field: the customer chooses it in Razorpay Checkout.


class SimulatePaymentRequest(BaseModel):
    outcome: Literal["success", "failure", "cancelled"]


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=1, max_length=500)


def get_booking(conn: sqlite3.Connection, booking_id: str) -> dict:
    row = conn.execute("SELECT * FROM sandbox_bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Booking was not found.")
    booking = json.loads(row["booking_json"])
    total = booking_total(booking)
    return {
        **booking,
        "status": row["status"],
        "subtotal_paise": booking["unit_price_paise"] * booking["ticket_count"],
        "total_paise": total,
        "subtotal": money(booking["unit_price_paise"] * booking["ticket_count"]),
        "convenience_fee": money(booking["convenience_fee_paise"]),
        "tax": money(booking["tax_paise"]),
        "total": money(total),
    }


def payment_result(conn: sqlite3.Connection, order_id: str) -> dict:
    order = conn.execute("SELECT * FROM sandbox_orders WHERE order_id = ?", (order_id,)).fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Payment order not found.")
    booking = get_booking(conn, order["booking_id"])
    payment = conn.execute("SELECT * FROM sandbox_payments WHERE order_id = ?", (order_id,)).fetchone()
    receipt = None
    if payment:
        receipt_row = conn.execute("SELECT receipt_number, issued_at FROM sandbox_receipts WHERE payment_id = ?", (payment["payment_id"],)).fetchone()
        if receipt_row:
            receipt = {"receipt_number": receipt_row["receipt_number"], "issued_at": receipt_row["issued_at"]}
    provider = order["provider"] or "mock"
    result = {
        "order_id": order["order_id"],
        "booking_id": order["booking_id"],
        "amount_paise": order["amount_paise"],
        "amount": money(order["amount_paise"]),
        "currency": order["currency"],
        "method": (payment["method"] if payment and payment["method"] else order["method"]),
        "status": order["status"],
        "created_at": order["created_at"],
        "booking": booking,
        "payment": None if not payment else {
            "payment_id": payment["payment_id"],
            "status": payment["status"],
            "outcome": payment["outcome"],
            "paid_at": payment["paid_at"],
            "created_at": payment["provider_created_at"] or payment["paid_at"],
            "method": payment["method"],
        },
        "receipt": receipt,
        "provider": "razorpay" if provider == "razorpay" else "local-mock",
        "sandbox": True,
        "live_payment": False,
        "message": "Razorpay Test Mode — no live money was charged." if provider == "razorpay" else "Local simulation only — no money was charged.",
    }
    if provider == "razorpay":
        result["key_id"] = os.getenv("RAZORPAY_KEY_ID", "").strip()
    return result


@app.get("/api/health")
def health() -> dict:
    provider = active_provider()
    configured = bool(os.getenv("RAZORPAY_KEY_ID", "").strip() and os.getenv("RAZORPAY_KEY_SECRET", "").strip())
    return {
        "status": "ok",
        "provider": "razorpay" if provider == "razorpay" else "local-mock",
        "mode": "test" if provider == "razorpay" else "local",
        "credentials_configured": configured if provider == "razorpay" else False,
        "live_payments": False,
    }


@app.post("/api/payments/bookings/demo")
def create_demo_booking() -> dict:
    """Create a fresh sample booking for each new checkout visit.

    The no-query-string demo page calls this endpoint on page load so a previous
    successful test transaction does not block the next test payment. Explicit
    booking_id links still resume the specific existing booking.
    """
    template = DEMO_BOOKINGS[0]
    token = secrets.token_hex(4).upper()
    booking = {
        **template,
        "booking_id": "demo-booking-" + secrets.token_hex(12),
        "booking_number": f"CIN-{datetime.now(timezone.utc).strftime('%y%m%d')}-{token}",
    }
    with db() as conn:
        conn.execute(
            "INSERT INTO sandbox_bookings(booking_id, booking_number, booking_json, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
            (booking["booking_id"], booking["booking_number"], json.dumps(booking), now_iso()),
        )
        return get_booking(conn, booking["booking_id"])


@app.get("/api/payments/booking/{booking_id}")
def read_booking(booking_id: str) -> dict:
    """Read booking summary and its most recent successful payment."""
    with db() as conn:
        booking = get_booking(conn, booking_id)
        last_order = conn.execute(
            "SELECT order_id FROM sandbox_orders WHERE booking_id=? AND status='successful' ORDER BY updated_at DESC LIMIT 1",
            (booking_id,),
        ).fetchone()
        if last_order:
            booking["latest_payment"] = payment_result(conn, last_order["order_id"])
        return booking


@app.post("/api/payments/orders")
def create_order(payload: CreateOrderRequest) -> dict:
    provider = active_provider()
    with db() as conn:
        booking = get_booking(conn, payload.booking_id)
        raw = conn.execute("SELECT status FROM sandbox_bookings WHERE booking_id=?", (payload.booking_id,)).fetchone()
        if raw["status"] == "confirmed":
            raise HTTPException(status_code=409, detail="This booking has already been paid.")
        # This module currently uses one shared demo environment without user
        # authentication. Block any unresolved Razorpay order before allowing a
        # new attempt, even when a refreshed page has created a new demo booking.
        # Once Features 01–04 are integrated, scope this guard to the authenticated
        # owner and their booking rather than globally across all customers.
        unresolved_order = None
        if provider == "razorpay":
            unresolved_order = conn.execute(
                "SELECT order_id FROM sandbox_orders WHERE provider='razorpay' AND status IN ('created','verification_pending','authorized') ORDER BY created_at DESC LIMIT 1",
            ).fetchone()
        if unresolved_order:
            raise HTTPException(
                status_code=409,
                detail=f"An existing payment order needs reconciliation: {unresolved_order['order_id']}. Check that same order before starting another payment.",
            )
        amount_paise = booking_total(booking)
        stamp = now_iso()
        if provider == "razorpay":
            client = get_razorpay_client()
            try:
                remote_order = client.order.create(data={
                    "amount": amount_paise,
                    "currency": booking.get("currency", "INR"),
                    "receipt": f"{booking['booking_number']}-{secrets.token_hex(4)}",
                    "notes": {
                        "booking_id": payload.booking_id,
                        "booking_number": booking["booking_number"],
                    },
                })
            except Exception as exc:
                # Do not include SDK request details or credentials in API responses.
                raise HTTPException(status_code=502, detail="Could not start secure payment. Check the payment configuration and internet connection.") from exc
            order_id = remote_order.get("id")
            if not order_id or remote_order.get("amount") != amount_paise:
                raise HTTPException(status_code=502, detail="Razorpay returned an unexpected order response.")
        else:
            order_id = "ord_sbx_" + secrets.token_hex(8)
        conn.execute(
            "INSERT INTO sandbox_orders(order_id, booking_id, amount_paise, currency, method, status, created_at, updated_at, provider) VALUES (?, ?, ?, ?, ?, 'created', ?, ?, ?)",
            (order_id, payload.booking_id, amount_paise, booking.get("currency", "INR"), "checkout", stamp, stamp, provider),
        )
        return payment_result(conn, order_id)


def fetch_payment_with_retries(client, payment_id: str, attempts: int = 3) -> dict:
    """Retry transient Razorpay API/network errors before declaring status unknown."""
    last_error = None
    for attempt in range(attempts):
        try:
            return client.payment.fetch(payment_id)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.4 * (2 ** attempt))
    raise RuntimeError("Could not fetch payment status from Razorpay") from last_error


def fetch_order_payments_with_retries(client, order_id: str, attempts: int = 3) -> dict:
    """Fetch provider-owned payment attempts for an order when Checkout gave no payment ID."""
    last_error = None
    for attempt in range(attempts):
        try:
            return client.order.payments(order_id)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.4 * (2 ** attempt))
    raise RuntimeError("Could not fetch payment attempts for this order") from last_error


def fetch_order_with_retries(client, order_id: str, attempts: int = 3) -> dict:
    """Fetch order totals/attempt counters as a second check before declaring no payment."""
    last_error = None
    for attempt in range(attempts):
        try:
            return client.order.fetch(order_id)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.4 * (2 ** attempt))
    raise RuntimeError("Could not fetch order status from Razorpay") from last_error


def provider_created_at_iso(provider_payment: dict) -> str | None:
    """Normalize Razorpay's Unix `created_at` value to a timezone-aware ISO timestamp."""
    value = provider_payment.get("created_at")
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def select_order_payment(items: list[dict], order_id: str) -> dict | None:
    """Prefer a captured/authorized attempt, otherwise reconcile the most recent one."""
    candidates = [item for item in items if isinstance(item, dict) and item.get("id") and item.get("order_id") == order_id]
    if not candidates:
        return None
    candidates.sort(key=lambda item: int(item.get("created_at") or 0), reverse=True)
    captured = next((item for item in candidates if str(item.get("status", "")).lower() == "captured"), None)
    if captured:
        return captured
    authorized = next((item for item in candidates if str(item.get("status", "")).lower() == "authorized"), None)
    return authorized or candidates[0]


def save_payment_state(
    conn: sqlite3.Connection,
    order: sqlite3.Row,
    payment_id: str,
    status: str,
    outcome: str,
    method: str | None = None,
    provider_created_at: str | None = None,
) -> dict:
    """Idempotently store provider state; retain the provider transaction timestamp when available."""
    stamp = now_iso()
    existing = conn.execute("SELECT * FROM sandbox_payments WHERE order_id=?", (order["order_id"],)).fetchone()
    if existing and existing["payment_id"] != payment_id:
        raise HTTPException(status_code=409, detail="A different payment is already associated with this order.")
    paid_at = stamp if status == "successful" else None
    resolved_method = (method or (existing["method"] if existing else None) or order["method"] or "unknown").lower()
    if existing:
        # Never downgrade an already-confirmed payment due to a stale/repeated callback.
        if existing["status"] == "successful":
            return payment_result(conn, order["order_id"])
        conn.execute(
            "UPDATE sandbox_payments SET status=?, outcome=?, paid_at=?, method=?, provider_created_at=COALESCE(?, provider_created_at) WHERE order_id=?",
            (status, outcome, paid_at, resolved_method, provider_created_at, order["order_id"]),
        )
    else:
        conn.execute(
            "INSERT INTO sandbox_payments(payment_id, order_id, amount_paise, currency, status, outcome, created_at, paid_at, method, provider_created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payment_id, order["order_id"], order["amount_paise"], order["currency"], status, outcome, stamp, paid_at, resolved_method, provider_created_at),
        )
    conn.execute("UPDATE sandbox_orders SET status=?, updated_at=? WHERE order_id=?", (status, stamp, order["order_id"]))
    if status == "successful":
        conn.execute("UPDATE sandbox_bookings SET status='confirmed' WHERE booking_id=?", (order["booking_id"],))
        conn.execute(
            "INSERT OR IGNORE INTO sandbox_receipts(receipt_number, payment_id, issued_at) VALUES (?, ?, ?)",
            ("RCT-RZP-" + secrets.token_hex(4).upper(), payment_id, stamp),
        )
    return payment_result(conn, order["order_id"])


def reconcile_provider_payment(
    conn: sqlite3.Connection,
    order: sqlite3.Row,
    payment_id: str,
    provider_payment: dict,
    client,
) -> dict:
    """Validate Razorpay's payment record and persist its authoritative state."""
    if provider_payment.get("order_id") != order["order_id"]:
        raise HTTPException(status_code=400, detail="Razorpay payment does not belong to this order.")
    if int(provider_payment.get("amount", -1)) != int(order["amount_paise"]):
        raise HTTPException(status_code=400, detail="Razorpay payment amount does not match the order.")
    if provider_payment.get("currency") != order["currency"]:
        raise HTTPException(status_code=400, detail="Razorpay payment currency does not match the order.")

    provider_status = str(provider_payment.get("status", "unknown")).lower()
    if provider_status == "authorized":
        # If dashboard auto-capture is disabled, attempt capture. If the response is
        # lost, fetch again; never treat an unknown capture result as a failed payment.
        try:
            captured = client.payment.capture(payment_id, {
                "amount": int(order["amount_paise"]),
                "currency": order["currency"],
            })
            if str(captured.get("status", "")).lower() == "captured":
                provider_payment = captured
            else:
                provider_payment = fetch_payment_with_retries(client, payment_id)
        except Exception:
            try:
                provider_payment = fetch_payment_with_retries(client, payment_id)
            except Exception:
                # The last known state is authorized, not failed. Save it so the
                # customer can retry verification instead of making a second payment.
                return save_payment_state(
                    conn, order, payment_id, "authorized",
                    "razorpay_authorized_capture_status_unknown",
                    str(provider_payment.get("method") or order["method"]),
                    provider_created_at_iso(provider_payment),
                )
        # Verify the fresh capture/fetch response against this order too.
        if provider_payment.get("order_id") != order["order_id"]:
            raise HTTPException(status_code=400, detail="Razorpay payment does not belong to this order.")
        if int(provider_payment.get("amount", -1)) != int(order["amount_paise"]) or provider_payment.get("currency") != order["currency"]:
            raise HTTPException(status_code=400, detail="Razorpay payment amount or currency does not match the order.")
        provider_status = str(provider_payment.get("status", "unknown")).lower()

    if provider_status == "captured":
        local_status = "successful"
    elif provider_status == "failed":
        local_status = "failed"
    elif provider_status == "authorized":
        local_status = "authorized"
    else:
        local_status = "verification_pending"
    return save_payment_state(
        conn, order, payment_id, local_status, f"razorpay_{provider_status}",
        str(provider_payment.get("method") or order["method"]),
        provider_created_at_iso(provider_payment),
    )


@app.get("/api/payments/orders/{order_id}")
def read_payment_order(order_id: str) -> dict:
    """Read an order's local payment state for a receipt or verification recovery."""
    with db() as conn:
        order = conn.execute("SELECT * FROM sandbox_orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Payment order not found.")
        return payment_result(conn, order_id)


@app.post("/api/payments/orders/{order_id}/verify")
def verify_razorpay_payment(order_id: str, payload: VerifyPaymentRequest) -> dict:
    """Verify callback signature, persist a pending attempt, then reconcile Razorpay status."""
    client = get_razorpay_client()
    if payload.razorpay_order_id != order_id:
        raise HTTPException(status_code=400, detail="The payment order ID does not match this checkout.")
    with db() as conn:
        order = conn.execute("SELECT * FROM sandbox_orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Payment order not found.")
        if order["provider"] != "razorpay":
            raise HTTPException(status_code=400, detail="This order was not created by Razorpay.")
        existing = conn.execute("SELECT * FROM sandbox_payments WHERE order_id=?", (order_id,)).fetchone()
        if existing:
            if existing["payment_id"] != payload.razorpay_payment_id:
                raise HTTPException(status_code=409, detail="A different payment is already associated with this order.")
            if existing["status"] in {"successful", "failed"}:
                return payment_result(conn, order_id)
        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payload.razorpay_payment_id,
                "razorpay_signature": payload.razorpay_signature,
            })
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Razorpay payment signature verification failed. The booking was not confirmed.") from exc

        # Persist the verified callback before calling Razorpay's status API. If the
        # next network call fails, refresh/retry can reconcile this exact transaction.
        save_payment_state(
            conn, order, payload.razorpay_payment_id, "verification_pending",
            "signature_verified_waiting_for_provider_status", existing["method"] if existing else order["method"],
        )
        try:
            provider_payment = fetch_payment_with_retries(client, payload.razorpay_payment_id)
        except Exception:
            # Return a pending result (HTTP 200), not a false failure/502. The UI
            # shows Retry verification and does not encourage another payment.
            return payment_result(conn, order_id)
        return reconcile_provider_payment(conn, order, payload.razorpay_payment_id, provider_payment, client)


class RecheckPaymentRequest(BaseModel):
    payment_id: str | None = Field(default=None, min_length=1, max_length=100)


@app.post("/api/payments/orders/{order_id}/recheck")
def recheck_razorpay_payment(order_id: str, payload: RecheckPaymentRequest) -> dict:
    """Retry status reconciliation for the same Razorpay payment, never create a new charge."""
    client = get_razorpay_client()
    with db() as conn:
        order = conn.execute("SELECT * FROM sandbox_orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Payment order not found.")
        if order["provider"] != "razorpay":
            raise HTTPException(status_code=400, detail="This order was not created by Razorpay.")
        existing = conn.execute("SELECT * FROM sandbox_payments WHERE order_id=?", (order_id,)).fetchone()
        payment_id = existing["payment_id"] if existing else payload.payment_id
        if existing and payload.payment_id and existing["payment_id"] != payload.payment_id:
            raise HTTPException(status_code=409, detail="Payment ID does not match the payment linked to this order.")
        if existing and existing["status"] in {"successful", "failed"}:
            return payment_result(conn, order_id)

        if not payment_id:
            # Checkout may be dismissed before it returns a payment ID. Ask Razorpay
            # for all attempts attached to this known order; never trust a browser's
            # claim that the payment failed or that no payment happened.
            try:
                collection = fetch_order_payments_with_retries(client, order_id)
            except Exception:
                stamp = now_iso()
                conn.execute("UPDATE sandbox_orders SET status='verification_pending', updated_at=? WHERE order_id=?", (stamp, order_id))
                return payment_result(conn, order_id)
            if not isinstance(collection, dict) or collection.get("entity") != "collection" or not isinstance(collection.get("items"), list):
                stamp = now_iso()
                conn.execute("UPDATE sandbox_orders SET status='verification_pending', updated_at=? WHERE order_id=?", (stamp, order_id))
                return payment_result(conn, order_id)
            items = collection["items"]
            provider_payment = select_order_payment(items, order_id)
            if not provider_payment:
                # Empty payment items alone can be a propagation delay. Require the
                # provider order itself to report zero attempts and zero paid amount.
                try:
                    provider_order = fetch_order_with_retries(client, order_id)
                    attempt_count = int(provider_order.get("attempts", -1))
                    amount_paid = int(provider_order.get("amount_paid", -1))
                    provider_order_status = str(provider_order.get("status", "")).lower()
                except Exception:
                    attempt_count, amount_paid, provider_order_status = -1, -1, "unknown"
                if not (attempt_count == 0 and amount_paid == 0 and provider_order_status == "created"):
                    stamp = now_iso()
                    conn.execute("UPDATE sandbox_orders SET status='verification_pending', updated_at=? WHERE order_id=?", (stamp, order_id))
                    return payment_result(conn, order_id)
                # Both provider reads confirm the order has no payment attempts and
                # no money paid, so a new checkout is safe after the user returns.
                stamp = now_iso()
                conn.execute("UPDATE sandbox_orders SET status='cancelled', updated_at=? WHERE order_id=?", (stamp, order_id))
                result = payment_result(conn, order_id)
                result["no_payment_attempt"] = True
                return result
            payment_id = str(provider_payment["id"])
        else:
            try:
                provider_payment = fetch_payment_with_retries(client, payment_id)
            except Exception:
                if existing:
                    save_payment_state(conn, order, payment_id, "verification_pending", "razorpay_status_fetch_temporarily_unavailable", existing["method"] or order["method"])
                    return payment_result(conn, order_id)
                # Keep the order blocked from creating a second order while provider
                # status is unknown. A retry checks this same order/payment ID.
                stamp = now_iso()
                conn.execute("UPDATE sandbox_orders SET status='verification_pending', updated_at=? WHERE order_id=?", (stamp, order_id))
                return payment_result(conn, order_id)
        return reconcile_provider_payment(conn, order, payment_id, provider_payment, client)


@app.post("/api/payments/orders/{order_id}/simulate")
def simulate_payment(order_id: str, payload: SimulatePaymentRequest) -> dict:
    """Mock-only callback. It is disabled completely when Razorpay is enabled."""
    with db() as conn:
        order = conn.execute("SELECT * FROM sandbox_orders WHERE order_id=?", (order_id,)).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Payment order not found.")
        if order["provider"] != "mock" or active_provider() != "mock":
            raise HTTPException(status_code=404, detail="Local simulation is disabled for Razorpay orders.")
        existing = conn.execute("SELECT * FROM sandbox_payments WHERE order_id=?", (order_id,)).fetchone()
        if existing:
            return payment_result(conn, order_id)
        if order["status"] != "created":
            return payment_result(conn, order_id)
        stamp = now_iso()
        payment_id = "pay_sbx_" + secrets.token_hex(8)
        status = "successful" if payload.outcome == "success" else ("failed" if payload.outcome == "failure" else "cancelled")
        paid_at = stamp if status == "successful" else None
        conn.execute(
            "INSERT INTO sandbox_payments(payment_id, order_id, amount_paise, currency, status, outcome, created_at, paid_at, method) VALUES (?, ?, ?, 'INR', ?, ?, ?, ?, ?)",
            (payment_id, order_id, order["amount_paise"], status, payload.outcome, stamp, paid_at, order["method"]),
        )
        conn.execute("UPDATE sandbox_orders SET status=?, updated_at=? WHERE order_id=?", (status, stamp, order_id))
        if payload.outcome == "success":
            conn.execute("UPDATE sandbox_bookings SET status='confirmed' WHERE booking_id=?", (order["booking_id"],))
            receipt_number = "RCT-SBX-" + secrets.token_hex(4).upper()
            conn.execute("INSERT INTO sandbox_receipts(receipt_number, payment_id, issued_at) VALUES (?, ?, ?)", (receipt_number, payment_id, stamp))
        return payment_result(conn, order_id)


@app.get("/api/payments/receipts/{receipt_number}")
def get_receipt(receipt_number: str) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT r.receipt_number, r.issued_at, p.payment_id, p.paid_at, p.amount_paise, p.currency, p.status, p.method, o.order_id, o.method AS requested_method, o.provider, o.booking_id, b.booking_json FROM sandbox_receipts r JOIN sandbox_payments p ON p.payment_id=r.payment_id JOIN sandbox_orders o ON o.order_id=p.order_id JOIN sandbox_bookings b ON b.booking_id=o.booking_id WHERE r.receipt_number=?",
            (receipt_number,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Receipt not found.")
        provider = row["provider"] or "mock"
        return {
            "receipt_number": row["receipt_number"],
            "issued_at": row["issued_at"],
            "payment_id": row["payment_id"],
            "order_id": row["order_id"],
            "booking_id": row["booking_id"],
            "amount": money(row["amount_paise"]),
            "currency": row["currency"],
            "payment_status": row["status"],
            "status": row["status"],
            "payment_method": row["method"] or row["requested_method"],
            "timestamp": row["paid_at"] or row["issued_at"],
            "booking": json.loads(row["booking_json"]),
            "provider": "razorpay" if provider == "razorpay" else "local-mock",
            "sandbox": True,
            "live_payment": False,
        }


# Serve the no-build frontend from the same origin so no Node/npm install is needed.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
