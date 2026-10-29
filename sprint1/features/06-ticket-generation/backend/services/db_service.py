"""
db_service.py — Database operations for F6: Ticket Generation & Verification.

All functions return None / False gracefully when the DB client is unavailable,
so the router can fall back to in-memory storage transparently.
"""

from datetime import datetime, timezone
from typing import Optional
from db import get_db


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload_to_record(payload: dict) -> dict:
    """Convert a BookingPayload dict into a tickets table row."""
    return {
        "booking_number": payload["booking_id"],
        "transaction_id": payload.get("transaction_id"),
        "user_id_str":    payload["user"]["user_id"],
        "user_name":      payload["user"]["name"],
        "user_email":     payload["user"]["email"],
        "event_id_str":   payload["event"]["event_id"],
        "event_name":     payload["event"]["name"],
        "event_date":     payload["event"]["date"],
        "event_time":     payload["event"]["time"],
        "event_venue":    payload["event"]["venue"],
        "seats": [
            {
                "seat_id": s["seat_id"],
                "row":     s["row"],
                "number":  s["number"],
                "tier":    s["tier"],
                "price":   s["price"],
            }
            for s in payload["seats"]
        ],
        "total_amount":   payload["total_amount"],
        "payment_status": payload.get("payment_status", "SUCCESS"),
        "booked_at":      payload.get("booked_at", _now_iso()),
        "is_used":        False,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def save_ticket(payload: dict) -> Optional[dict]:
    """
    Upsert a confirmed ticket into the `tickets` table.
    Returns the saved row, or None if DB is unavailable.
    """
    db = get_db()
    if db is None:
        return None

    record = _payload_to_record(payload)

    try:
        result = (
            db.table("tickets")
            .upsert(record, on_conflict="booking_number")
            .execute()
        )
        row = result.data[0] if result.data else None
        if row:
            print(f"[DB] ✅ Ticket saved: {payload['booking_id']}")
        return row
    except Exception as exc:
        print(f"[DB] ⚠️  save_ticket failed: {exc}")
        return None


def get_ticket(booking_number: str) -> Optional[dict]:
    """
    Fetch a ticket row by booking_number.
    Returns None if not found or DB is unavailable.
    """
    db = get_db()
    if db is None:
        return None

    try:
        result = (
            db.table("tickets")
            .select("*")
            .eq("booking_number", booking_number)
            .maybe_single()
            .execute()
        )
        return result.data
    except Exception as exc:
        print(f"[DB] ⚠️  get_ticket failed: {exc}")
        return None


def mark_ticket_used(booking_number: str) -> Optional[dict]:
    """
    Mark a ticket as used (first scan at venue entry).
    Only updates rows where is_used = false — returns None if already scanned.
    """
    db = get_db()
    if db is None:
        return None

    used_at = _now_iso()
    try:
        result = (
            db.table("tickets")
            .update({"is_used": True, "used_at": used_at})
            .eq("booking_number", booking_number)
            .eq("is_used", False)         # atomic: only flip once
            .execute()
        )
        if result.data:
            print(f"[DB] ✅ Ticket scanned: {booking_number} at {used_at}")
            return result.data[0]
        # No rows updated → already used
        return None
    except Exception as exc:
        print(f"[DB] ⚠️  mark_ticket_used failed: {exc}")
        return None


def ticket_exists(booking_number: str) -> bool:
    """Quick existence check — used for idempotency in /confirm."""
    db = get_db()
    if db is None:
        return False

    try:
        result = (
            db.table("tickets")
            .select("booking_number")
            .eq("booking_number", booking_number)
            .maybe_single()
            .execute()
        )
        return result.data is not None
    except Exception:
        return False
