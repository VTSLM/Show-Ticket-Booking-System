"""
fixture_seats.py
================
Phase 1 — hand-written fixture data for seat-selection.

Seat shape matches the shared contract:
  {
    "id":        str   — e.g. "R1-S1"
    "row":       str   — e.g. "R1"
    "number":    int   — seat number within row
    "section":   str   — "VIP" | "PREMIUM" | "GENERAL"
    "status":    str   — "available" | "locked" | "booked" | "blocked"
    "price":     int   — price in INR
    "locked_by": str | None  — userId who holds the lock
    "expires_at": str | None — ISO-8601 expiry timestamp of lock
  }

Swap this for a real DB query later — one-line change at the call-site.
"""

from datetime import datetime, timezone
from copy import deepcopy
from typing import Optional

# ---------------------------------------------------------------------------
# Static fixture — 30 seats across 3 sections, multiple statuses
# ---------------------------------------------------------------------------

_SEAT_FIXTURE = [
    # ── VIP SECTION (Row V1, seats 1-6) ──────────────────────────────────
    {"id": "V1-S1", "row": "V1", "number": 1, "section": "VIP",     "status": "available", "price": 1500, "locked_by": None, "expires_at": None},
    {"id": "V1-S2", "row": "V1", "number": 2, "section": "VIP",     "status": "available", "price": 1500, "locked_by": None, "expires_at": None},
    {"id": "V1-S3", "row": "V1", "number": 3, "section": "VIP",     "status": "booked",    "price": 1500, "locked_by": None, "expires_at": None},
    {"id": "V1-S4", "row": "V1", "number": 4, "section": "VIP",     "status": "available", "price": 1500, "locked_by": None, "expires_at": None},
    {"id": "V1-S5", "row": "V1", "number": 5, "section": "VIP",     "status": "blocked",   "price": 1500, "locked_by": None, "expires_at": None},
    {"id": "V1-S6", "row": "V1", "number": 6, "section": "VIP",     "status": "available", "price": 1500, "locked_by": None, "expires_at": None},

    # ── PREMIUM SECTION (Rows P1 & P2, 6 seats each) ─────────────────────
    {"id": "P1-S1", "row": "P1", "number": 1, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P1-S2", "row": "P1", "number": 2, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P1-S3", "row": "P1", "number": 3, "section": "PREMIUM", "status": "locked",    "price": 900, "locked_by": "user-demo-other", "expires_at": None},
    {"id": "P1-S4", "row": "P1", "number": 4, "section": "PREMIUM", "status": "booked",    "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P1-S5", "row": "P1", "number": 5, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P1-S6", "row": "P1", "number": 6, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},

    {"id": "P2-S1", "row": "P2", "number": 1, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P2-S2", "row": "P2", "number": 2, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P2-S3", "row": "P2", "number": 3, "section": "PREMIUM", "status": "booked",    "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P2-S4", "row": "P2", "number": 4, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P2-S5", "row": "P2", "number": 5, "section": "PREMIUM", "status": "blocked",   "price": 900, "locked_by": None, "expires_at": None},
    {"id": "P2-S6", "row": "P2", "number": 6, "section": "PREMIUM", "status": "available", "price": 900, "locked_by": None, "expires_at": None},

    # ── GENERAL SECTION (Rows G1, G2, G3 — 6 seats each) ────────────────
    {"id": "G1-S1", "row": "G1", "number": 1, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G1-S2", "row": "G1", "number": 2, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G1-S3", "row": "G1", "number": 3, "section": "GENERAL", "status": "booked",    "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G1-S4", "row": "G1", "number": 4, "section": "GENERAL", "status": "booked",    "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G1-S5", "row": "G1", "number": 5, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G1-S6", "row": "G1", "number": 6, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},

    {"id": "G2-S1", "row": "G2", "number": 1, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G2-S2", "row": "G2", "number": 2, "section": "GENERAL", "status": "locked",    "price": 400, "locked_by": "user-demo-other", "expires_at": None},
    {"id": "G2-S3", "row": "G2", "number": 3, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G2-S4", "row": "G2", "number": 4, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G2-S5", "row": "G2", "number": 5, "section": "GENERAL", "status": "blocked",   "price": 400, "locked_by": None, "expires_at": None},
    {"id": "G2-S6", "row": "G2", "number": 6, "section": "GENERAL", "status": "available", "price": 400, "locked_by": None, "expires_at": None},
]

# In-memory seat store — acts as the "database" for Phase 1
# Key: seat_id -> seat dict
_seat_store: dict[str, dict] = {seat["id"]: deepcopy(seat) for seat in _SEAT_FIXTURE}

# In-memory booking store
_booking_store: dict[str, dict] = {}

# Booking counter (for generating booking IDs)
_booking_counter = [0]


# ---------------------------------------------------------------------------
# Data access helpers (replace the bodies with real DB calls for Phase 2+)
# ---------------------------------------------------------------------------

def get_all_seats(show_id: str) -> list[dict]:
    """Return current seat list for a show.
    PHASE-1: ignores show_id, returns fixture data.
    PHASE-2: SELECT * FROM show_seats WHERE show_id = $1
    """
    return [deepcopy(s) for s in _seat_store.values()]


def get_seat(seat_id: str) -> Optional[dict]:
    seat = _seat_store.get(seat_id)
    return deepcopy(seat) if seat else None


def atomic_lock_seats(seat_ids: list[str], user_id: str, expires_at: str) -> tuple[bool, list[str]]:
    """
    Compare-and-swap lock for ALL requested seats.
    Returns (success, failed_seat_ids).
    
    Atomicity guarantee:
    - Check ALL seats are 'available' FIRST (read phase).
    - Only if ALL pass, write the lock (write phase).
    - If ANY fail the check, the entire operation fails — no partial locks.
    
    PHASE-1: in-memory dict with a lock-all-or-none approach.
    PHASE-2: Use a DB transaction with SELECT FOR UPDATE + conditional UPDATE.
    """
    # Step 1: Verify all exist and are available
    failed: list[str] = []
    for sid in seat_ids:
        seat = _seat_store.get(sid)
        if not seat or seat["status"] != "available":
            failed.append(sid)

    if failed:
        return False, failed

    # Step 2: Atomically lock all (write phase — only reached if ALL passed)
    for sid in seat_ids:
        _seat_store[sid]["status"] = "locked"
        _seat_store[sid]["locked_by"] = user_id
        _seat_store[sid]["expires_at"] = expires_at

    return True, []


def release_seats(seat_ids: list[str], user_id: str) -> bool:
    """Release locked seats back to available.
    Only releases seats that are locked by this specific user.
    """
    for sid in seat_ids:
        seat = _seat_store.get(sid)
        if seat and seat["status"] == "locked" and seat["locked_by"] == user_id:
            seat["status"] = "available"
            seat["locked_by"] = None
            seat["expires_at"] = None
    return True


def confirm_seats(seat_ids: list[str], user_id: str) -> tuple[bool, str]:
    """
    Atomically transition locked → booked for all seats owned by user.
    Returns (success, booking_id).
    
    Policy: If ANY seat's lock is expired or owned by someone else,
    reject the entire confirmation (fail-safe — user must re-select).
    """
    now = datetime.now(timezone.utc)

    # Verify all seats are still locked by this user and not expired
    for sid in seat_ids:
        seat = _seat_store.get(sid)
        if not seat:
            return False, ""
        if seat["status"] != "locked" or seat["locked_by"] != user_id:
            return False, ""
        # Check expiry
        if seat["expires_at"]:
            expiry = datetime.fromisoformat(seat["expires_at"])
            if now > expiry:
                # Lock expired — release it and reject
                seat["status"] = "available"
                seat["locked_by"] = None
                seat["expires_at"] = None
                return False, ""

    # All good — confirm booking
    for sid in seat_ids:
        _seat_store[sid]["status"] = "booked"
        _seat_store[sid]["locked_by"] = None
        _seat_store[sid]["expires_at"] = None

    _booking_counter[0] += 1
    booking_id = f"BKG-{_booking_counter[0]:05d}"
    total = sum(_seat_store[sid]["price"] for sid in seat_ids)
    
    _booking_store[booking_id] = {
        "booking_id": booking_id,
        "user_id": user_id,
        "seat_ids": seat_ids,
        "total_price": total,
        "status": "confirmed",
        "created_at": now.isoformat(),
    }

    return True, booking_id


def cancel_booking(booking_id: str, user_id: str) -> bool:
    """Cancel a confirmed booking — release seats back to available (FR13)."""
    booking = _booking_store.get(booking_id)
    if not booking:
        return False
    if booking["user_id"] != user_id:
        return False
    if booking["status"] != "confirmed":
        return False

    # Return seats to available pool
    for sid in booking["seat_ids"]:
        seat = _seat_store.get(sid)
        if seat and seat["status"] == "booked":
            seat["status"] = "available"
            seat["locked_by"] = None
            seat["expires_at"] = None

    booking["status"] = "cancelled"
    return True


def sweep_expired_locks() -> list[str]:
    """
    Background sweeper — finds expired locks and releases them.
    Called by the APScheduler job in main.py.
    Returns list of seat IDs that were released.
    """
    now = datetime.now(timezone.utc)
    released: list[str] = []
    for seat in _seat_store.values():
        if seat["status"] == "locked" and seat["expires_at"]:
            expiry = datetime.fromisoformat(seat["expires_at"])
            if now > expiry:
                seat["status"] = "available"
                seat["locked_by"] = None
                seat["expires_at"] = None
                released.append(seat["id"])
    return released


def get_booking(booking_id: str) -> Optional[dict]:
    return deepcopy(_booking_store.get(booking_id))


def get_user_bookings(user_id: str) -> list[dict]:
    return [deepcopy(b) for b in _booking_store.values() if b["user_id"] == user_id]
