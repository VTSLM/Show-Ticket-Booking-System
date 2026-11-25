from unittest.mock import AsyncMock, MagicMock

import pytest

from routers.notifications import get_my_notifications


@pytest.mark.asyncio
async def test_notification_json_payload_is_returned_as_an_object():
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{
        "id": "notification-1",
        "event_name": "transfer.received",
        "payload": '{"event_title": "Concert", "sender_name": "Asha"}',
        "read_at": None,
        "created_at": None,
    }])
    conn.fetchval = AsyncMock(return_value=1)

    result = await get_my_notifications(limit=15, current_user={"id": "user-1"}, conn=conn)

    assert result["unread_count"] == 1
    assert result["notifications"][0]["payload"] == {"event_title": "Concert", "sender_name": "Asha"}
    assert conn.fetch.await_args.args[1:] == ("user-1", 15)


@pytest.mark.asyncio
async def test_notification_existing_object_payload_is_preserved():
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[{"event_name": "transfer.accepted", "payload": {"booking_id": "booking-1"}}])
    conn.fetchval = AsyncMock(return_value=0)

    result = await get_my_notifications(current_user={"id": "user-1"}, conn=conn)

    assert result["notifications"][0]["payload"] == {"booking_id": "booking-1"}
