from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import asyncpg
import json
import uuid
from datetime import datetime, timezone
from database import get_conn, get_pool
from dependencies import get_current_user

router = APIRouter(prefix="/api/seats", tags=["seats"])

# ---- WebSocket Connection Manager ----
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}  # show_id -> [ws]

    async def connect(self, show_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(show_id, []).append(ws)

    def disconnect(self, show_id: str, ws: WebSocket):
        if show_id in self.active:
            self.active[show_id].discard(ws) if isinstance(self.active[show_id], set) else \
                (self.active[show_id].remove(ws) if ws in self.active[show_id] else None)

    async def broadcast(self, show_id: str, message: dict):
        dead = []
        for ws in self.active.get(show_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(show_id, ws)

manager = ConnectionManager()

LOCK_DURATION_MINUTES = 10

# ---- REST endpoints ----
@router.get("/{show_id}/map")
async def get_seat_map(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    # Release expired locks in DB before returning the map
    await conn.execute(
        """UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL
           WHERE show_id=$1 AND status='locked' AND locked_until < NOW()""",
        show_id
    )
    rows = await conn.fetch(
        """SELECT ss.id as show_seat_id, ss.status, ss.price,
                  s.row_label, s.seat_number, s.seat_type
           FROM show_seats ss
           JOIN seats s ON s.id = ss.seat_id
           WHERE ss.show_id = $1
           ORDER BY s.row_label, s.seat_number""",
        show_id
    )
    return [dict(r) for r in rows]


class LockRequest(BaseModel):
    seat_ids: List[str]

@router.post("/{show_id}/lock")
async def lock_seats(
    show_id: str,
    req: LockRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    if not req.seat_ids:
        raise HTTPException(status_code=400, detail="No seats provided")
    user_id = str(current_user["id"])
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    locked_until = now + timedelta(minutes=LOCK_DURATION_MINUTES)

    # Try to lock requested seats
    locked = []
    failed = []
    for seat_id in req.seat_ids:
        result = await conn.execute(
            """UPDATE show_seats SET status='locked', locked_by=$3, locked_until=$4
               WHERE id=$1 AND show_id=$2 AND status='available'""",
            seat_id, show_id, user_id, locked_until
        )
        if result == "UPDATE 1":
            locked.append(seat_id)
        else:
            failed.append(seat_id)

    if failed:
        # Rollback
        await conn.execute(
            """UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL
               WHERE id=ANY($1::uuid[]) AND locked_by=$2""",
            locked, user_id
        )
        raise HTTPException(status_code=409, detail=f"Seats unavailable: {failed}")

    await manager.broadcast(show_id, {"type": "lock", "seat_ids": locked, "user_id": user_id})
    return {"locked": locked, "locked_until": locked_until.isoformat()}


@router.post("/{show_id}/release")
async def release_seats(
    show_id: str,
    req: LockRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    user_id = str(current_user["id"])
    await conn.execute(
        """UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL
           WHERE id=ANY($1::uuid[]) AND show_id=$2 AND locked_by=$3 AND status='locked'""",
        req.seat_ids, show_id, user_id
    )
    await manager.broadcast(show_id, {"type": "release", "seat_ids": req.seat_ids})
    return {"released": req.seat_ids}


# ---- WebSocket ----
@router.websocket("/{show_id}/ws")
async def seat_ws(show_id: str, websocket: WebSocket):
    await manager.connect(show_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send pings or requests
    except WebSocketDisconnect:
        manager.disconnect(show_id, websocket)
