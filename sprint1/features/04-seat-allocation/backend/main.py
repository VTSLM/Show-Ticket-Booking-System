"""
main.py
=======
FastAPI entry-point for the Seat Allocation feature (Sprint 1, Feature 04).

Phases covered:
  Phase 1 - Fixture data
  Phase 2 - Seat map API
  Phase 3 - Atomic lock API
  Phase 4 - Hold countdown & auto-expiry sweeper
  Phase 5 - Confirm & release (cancel)
  Phase 6 - Real-time WebSocket broadcasts
  Phase 7 - Error/expired-lock responses

Run locally:
  pip install -r requirements.txt
  uvicorn main:app --reload --port 8001
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import asyncio
import logging

from fixture_seats import (
    get_all_seats,
    get_seat,
    atomic_lock_seats,
    release_seats,
    confirm_seats,
    cancel_booking,
    sweep_expired_locks,
    get_booking,
    get_user_bookings,
)
from ws_manager import manager

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Seat Allocation API",
    description="Sprint 1 – Feature 04: Seat Selection & Locking",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Lock down to specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
LOCK_DURATION_MINUTES = 5
MAX_SEATS_PER_BOOKING = 6      # Shared contract cap
LOCK_SWEEP_INTERVAL_SECONDS = 30  # How often the sweeper runs


# ─────────────────────────────────────────────────────────────────────────────
# Background sweeper task — releases expired locks automatically (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def start_lock_sweeper():
    """Start background task that sweeps expired locks every 30 seconds."""
    asyncio.create_task(lock_sweeper_loop())


async def lock_sweeper_loop():
    while True:
        await asyncio.sleep(LOCK_SWEEP_INTERVAL_SECONDS)
        released = sweep_expired_locks()
        if released:
            logger.info(f"Sweeper released {len(released)} expired locks: {released}")
            # Broadcast the release to all active WS viewers
            # NOTE: We broadcast against a demo show_id for Phase 1.
            # In Phase 2, track show_id in the lock record and broadcast per show.
            await manager.broadcast_lock_expiry("show-demo-001", released)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────
class LockRequest(BaseModel):
    seat_ids: list[str]
    user_id: str
    show_id: str


class ReleaseRequest(BaseModel):
    seat_ids: list[str]
    user_id: str
    show_id: str


class ConfirmRequest(BaseModel):
    seat_ids: list[str]
    user_id: str
    show_id: str


class CancelRequest(BaseModel):
    booking_id: str
    user_id: str


# ─────────────────────────────────────────────────────────────────────────────
# REST endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "seat-allocation"}


@app.get("/api/shows/{show_id}/seats")
async def get_seats(show_id: str):
    """
    Phase 2: Return all seats for a show with current statuses.
    Frontend uses this to render the seat map on load.
    """
    seats = get_all_seats(show_id)
    return {
        "show_id": show_id,
        "max_seats_per_booking": MAX_SEATS_PER_BOOKING,
        "seats": seats,
    }


@app.post("/api/seats/lock")
async def lock_seats(req: LockRequest):
    """
    Phase 3: Atomic compare-and-swap lock.
    
    Guarantees: Lock ALL requested seats or NONE.
    Uses atomic check-then-set to prevent race conditions.
    
    Returns 409 if any seat is unavailable (someone else grabbed it).
    Frontend should show the specific conflicting seats.
    """
    if len(req.seat_ids) == 0:
        raise HTTPException(status_code=400, detail="No seats provided.")
    if len(req.seat_ids) > MAX_SEATS_PER_BOOKING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot book more than {MAX_SEATS_PER_BOOKING} seats at once.",
        )

    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_DURATION_MINUTES)).isoformat()
    success, failed = atomic_lock_seats(req.seat_ids, req.user_id, expires_at)

    if not success:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Some seats are no longer available. Please re-select.",
                "failed_seat_ids": failed,
            },
        )

    # Broadcast seat status changes to all WebSocket viewers (Phase 6)
    for seat_id in req.seat_ids:
        seat = get_seat(seat_id)
        if seat:
            await manager.broadcast_seat_update(req.show_id, seat)

    return {
        "success": True,
        "locked_seat_ids": req.seat_ids,
        "expires_at": expires_at,
        "lock_duration_minutes": LOCK_DURATION_MINUTES,
    }


@app.post("/api/seats/release")
async def release_locked_seats(req: ReleaseRequest):
    """
    Phase 4 (manual): User cancels selection before timer expires.
    Releases lock immediately — same transition as auto-expiry, user-triggered.
    """
    release_seats(req.seat_ids, req.user_id)

    # Broadcast release to all WS viewers
    for seat_id in req.seat_ids:
        seat = get_seat(seat_id)
        if seat:
            await manager.broadcast_seat_update(req.show_id, seat)

    return {"success": True, "released_seat_ids": req.seat_ids}


@app.post("/api/seats/confirm")
async def confirm_booking(req: ConfirmRequest):
    """
    Phase 5: Post-payment confirmation.
    
    Re-verifies lock is still valid and belongs to this user.
    Atomically transitions locked → booked.
    
    Returns 409 if lock expired — frontend must redirect user back to seat selection
    with a clear 'Your hold expired' message (Phase 7 UX).
    """
    success, booking_id = confirm_seats(req.seat_ids, req.user_id)

    if not success:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Your seat hold has expired. Please go back and re-select your seats.",
                "error_code": "LOCK_EXPIRED",
            },
        )

    # Broadcast confirmed seats to all WS viewers
    for seat_id in req.seat_ids:
        seat = get_seat(seat_id)
        if seat:
            await manager.broadcast_seat_update(req.show_id, seat)

    booking = get_booking(booking_id)
    return {
        "success": True,
        "booking_id": booking_id,
        "booking": booking,
    }


@app.post("/api/bookings/cancel")
async def cancel_booking_endpoint(req: CancelRequest):
    """
    Phase 5 (cancellation / FR13): Cancel confirmed booking.
    Transitions booked → available so seat re-enters the pool.
    """
    booking = get_booking(req.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    success = cancel_booking(req.booking_id, req.user_id)
    if not success:
        raise HTTPException(status_code=403, detail="Cannot cancel this booking.")

    # Broadcast seat release to all WS viewers
    show_id = "show-demo-001"  # Phase 2: store show_id in booking record
    for seat_id in booking["seat_ids"]:
        seat = get_seat(seat_id)
        if seat:
            await manager.broadcast_seat_update(show_id, seat)

    return {"success": True, "message": "Booking cancelled and seats released."}


@app.get("/api/bookings/{booking_id}")
async def get_booking_endpoint(booking_id: str, user_id: str = Query(...)):
    booking = get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    return booking


@app.get("/api/users/{user_id}/bookings")
async def get_user_bookings_endpoint(user_id: str):
    return {"user_id": user_id, "bookings": get_user_bookings(user_id)}


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket endpoint — real-time seat map updates (Phase 6)
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws/{show_id}")
async def websocket_endpoint(websocket: WebSocket, show_id: str):
    """
    WebSocket endpoint for real-time seat status updates.
    
    Frontend connects once and listens for SEAT_UPDATE messages.
    Server pushes only the changed seat — not the whole layout.
    
    Message format:
      { "type": "SEAT_UPDATE", "seat_id": "G1-S3", "status": "locked" }
    """
    await manager.connect(websocket, show_id)
    try:
        while True:
            # Keep connection alive — frontend doesn't need to send anything
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, show_id)
