"""
ws_manager.py
=============
WebSocket connection manager for real-time seat status broadcasts (Phase 6).

Each connected frontend client opens a WebSocket to /ws/{show_id}.
When any seat status changes, we broadcast ONLY that seat's new status
to all clients watching the same show — not the entire layout.

This keeps the payload tiny and avoids unnecessary re-renders.
"""

from fastapi import WebSocket
from collections import defaultdict
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by show_id."""

    def __init__(self):
        # show_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, show_id: str):
        await websocket.accept()
        self._connections[show_id].add(websocket)
        logger.info(f"WS connected: show={show_id}, total={len(self._connections[show_id])}")

    def disconnect(self, websocket: WebSocket, show_id: str):
        self._connections[show_id].discard(websocket)
        if not self._connections[show_id]:
            del self._connections[show_id]
        logger.info(f"WS disconnected: show={show_id}")

    async def broadcast_seat_update(self, show_id: str, seat: dict):
        """
        Broadcast a single seat's updated status to all viewers of this show.
        Sends only the fields needed to update the grid — not the full seat list.
        """
        payload = json.dumps({
            "type": "SEAT_UPDATE",
            "seat_id": seat["id"],
            "status": seat["status"],
        })

        dead: list[WebSocket] = []
        for ws in list(self._connections.get(show_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws, show_id)

    async def broadcast_lock_expiry(self, show_id: str, seat_ids: list[str]):
        """Notify all viewers that specific seats became available again (lock expired)."""
        for seat_id in seat_ids:
            await self.broadcast_seat_update(show_id, {"id": seat_id, "status": "available"})


# Singleton — imported in main.py and router files
manager = ConnectionManager()
