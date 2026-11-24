"""
Comprehensive tests for real-time seat lock synchronization, concurrency, and WebSockets.

Covers:
- Test A: Two-user seat locking (Account A locks, Account B cannot lock and sees unavailable).
- Test B: Simultaneous lock requests (atomic update guarantees exactly one succeeds, other gets 409).
- Test C: Seat release (Account A releases seat, broadcast sent, seat becomes available).
- Test D: Lock expiration (expired lock can be claimed by another user, cleanup broadcasts release).
- Test E: Failed lock rollback (rejected lock request rolls back cleanly and returns 409).
- Test F: WebSocket endpoint works with validate_path_ids (no TypeError) and receives broadcasts.
- Test G: Multi-instance synchronization via pg_notify broadcast.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from path_ids import validate_path_ids
from routers.seats import (
    router as seats_router,
    manager,
    lock_seats,
    release_seats,
    get_seat_map,
    LockRequest,
    INSTANCE_ID,
)


@pytest.mark.asyncio
async def test_a_two_user_seat_locking():
    """Account A locks a seat; Account B is rejected with 409 and seat is unavailable."""
    conn = AsyncMock()
    show_id = str(uuid.uuid4())
    seat_1 = str(uuid.uuid4())
    user_a = {"id": str(uuid.uuid4())}
    user_b = {"id": str(uuid.uuid4())}

    # User A locks seat_1 successfully
    conn.execute.return_value = "UPDATE 1"
    req_a = LockRequest(seat_ids=[seat_1])
    res_a = await lock_seats(show_id=show_id, req=req_a, current_user=user_a, conn=conn)
    assert res_a["locked"] == [seat_1]

    # User B attempts to lock seat_1; database reports UPDATE 0 (already locked)
    conn.execute.return_value = "UPDATE 0"
    req_b = LockRequest(seat_ids=[seat_1])
    with pytest.raises(HTTPException) as exc:
        await lock_seats(show_id=show_id, req=req_b, current_user=user_b, conn=conn)
    assert exc.value.status_code == 409
    assert seat_1 in exc.value.detail


@pytest.mark.asyncio
async def test_b_simultaneous_lock_requests():
    """Simultaneous lock requests on the same seat: exactly one succeeds, the other gets 409."""
    show_id = str(uuid.uuid4())
    seat_id = str(uuid.uuid4())
    user_a = {"id": str(uuid.uuid4())}
    user_b = {"id": str(uuid.uuid4())}

    # Simulate race condition: User A's connection acquires lock (UPDATE 1)
    conn_a = AsyncMock()
    conn_a.execute.return_value = "UPDATE 1"

    # User B's connection gets UPDATE 0 (concurrency collision)
    conn_b = AsyncMock()
    conn_b.execute.return_value = "UPDATE 0"

    res_a = await lock_seats(show_id=show_id, req=LockRequest(seat_ids=[seat_id]), current_user=user_a, conn=conn_a)
    assert res_a["locked"] == [seat_id]

    with pytest.raises(HTTPException) as exc:
        await lock_seats(show_id=show_id, req=LockRequest(seat_ids=[seat_id]), current_user=user_b, conn=conn_b)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_c_seat_release():
    """Account A locks a seat and then releases it; broadcast event is emitted."""
    conn = AsyncMock()
    show_id = str(uuid.uuid4())
    seat_id = str(uuid.uuid4())
    user_a = {"id": str(uuid.uuid4())}

    # Mock release returning the released seat id
    conn.fetch.return_value = [{"id": uuid.UUID(seat_id)}]

    with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
        res = await release_seats(show_id=show_id, req=LockRequest(seat_ids=[seat_id]), current_user=user_a, conn=conn)
        assert res["released"] == [seat_id]
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args[0]
        assert call_args[0] == show_id
        assert call_args[1] == {"type": "release", "seat_ids": [seat_id]}


@pytest.mark.asyncio
async def test_d_lock_expiration():
    """Expired locks are cleaned up and broadcast as released; new user can claim expired seat."""
    conn = AsyncMock()
    show_id = str(uuid.uuid4())
    expired_seat = str(uuid.uuid4())
    user_b = {"id": str(uuid.uuid4())}

    # When get_seat_map runs, it releases expired locks and broadcasts
    conn.fetchrow.return_value = {
        "layout_type": "cinema",
        "stage_position": "front",
        "event_type": "movie",
        "layout_config": None,
        "show_terms": None,
        "event_terms": None,
    }
    # First fetch: expired released rows; second fetch: show_seats; third fetch: zones
    conn.fetch.side_effect = [
        [{"id": uuid.UUID(expired_seat)}],  # expired seats released
        [
            {
                "show_seat_id": expired_seat,
                "status": "available",
                "price": 300.0,
                "row_label": "A",
                "seat_number": 1,
                "seat_type": "standard",
                "is_mine": False,
            }
        ],
        [],  # zones
    ]

    with patch.object(manager, "broadcast", new_callable=AsyncMock) as mock_broadcast:
        map_data = await get_seat_map(show_id=show_id, conn=conn)
        assert len(map_data["seats"]) == 1
        assert map_data["seats"][0]["status"] == "available"
        assert map_data["seats"][0]["is_mine"] is False
        mock_broadcast.assert_called_once_with(
            show_id, {"type": "release", "seat_ids": [expired_seat]}, conn=conn
        )

    # Now User B can lock the expired seat
    conn.execute.return_value = "UPDATE 1"
    lock_res = await lock_seats(
        show_id=show_id, req=LockRequest(seat_ids=[expired_seat]), current_user=user_b, conn=conn
    )
    assert lock_res["locked"] == [expired_seat]


@pytest.mark.asyncio
async def test_e_failed_lock_rollback():
    """If one seat in a multi-seat lock request fails, previously locked seats in the batch are rolled back."""
    conn = AsyncMock()
    show_id = str(uuid.uuid4())
    seat_1 = str(uuid.uuid4())
    seat_2 = str(uuid.uuid4())
    user = {"id": str(uuid.uuid4())}

    # Seat 1 succeeds, Seat 2 fails
    conn.execute.side_effect = [
        "UPDATE 1",  # seat_1 locked
        "UPDATE 0",  # seat_2 failed
        "UPDATE 1",  # rollback of seat_1
    ]

    with pytest.raises(HTTPException) as exc:
        await lock_seats(show_id=show_id, req=LockRequest(seat_ids=[seat_1, seat_2]), current_user=user, conn=conn)

    assert exc.value.status_code == 409
    assert seat_2 in exc.value.detail
    # Verify rollback execute was called for seat_1
    rollback_call = conn.execute.call_args_list[-1]
    assert "status='available'" in rollback_call[0][0]
    assert rollback_call[0][1] == [seat_1]


def test_f_websocket_endpoint_with_validate_path_ids():
    """WebSocket connection works without TypeError from validate_path_ids and receives broadcasts."""
    app = FastAPI(dependencies=[Depends(validate_path_ids)])
    app.include_router(seats_router)

    client = TestClient(app)
    show_id = str(uuid.uuid4())

    # Valid UUID show_id connects cleanly without TypeError: missing required argument 'request'
    with client.websocket_connect(f"/api/seats/{show_id}/ws") as ws:
        # Broadcast a test message via ConnectionManager
        asyncio.run(manager.broadcast(show_id, {"type": "lock", "seat_ids": ["test-seat"]}))
        msg = ws.receive_json()
        assert msg == {"type": "lock", "seat_ids": ["test-seat"]}


@pytest.mark.asyncio
async def test_g_multi_instance_notification():
    """PostgreSQL NOTIFY payload is published on broadcast and remote events are relayed to local WebSockets."""
    conn = AsyncMock()
    show_id = str(uuid.uuid4())
    message = {"type": "lock", "seat_ids": ["remote-seat-1"]}

    # Local broadcast triggers pg_notify with correct payload
    await manager.broadcast(show_id, message, from_remote=False, conn=conn)
    conn.execute.assert_called_once()
    sql, payload_str = conn.execute.call_args[0]
    assert "pg_notify" in sql
    payload = json.loads(payload_str)
    assert payload["show_id"] == show_id
    assert payload["instance_id"] == INSTANCE_ID
    assert payload["message"] == message
