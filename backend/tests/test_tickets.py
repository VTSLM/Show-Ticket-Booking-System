from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException

from routers.tickets import (
    verify_ticket,
    scan_ticket,
    scan_ticket_by_booking_id,
    TicketScanRequest,
)

SAMPLE_BOOKING_ID = "408e08d1-d2f6-4d0f-a9cb-b295f70a7b45"
SAMPLE_TICKET_ID = "99999999-9999-9999-9999-999999999999"


def make_conn(fetch_rows=None, fetchrow_result=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    return conn


@pytest.mark.asyncio
async def test_verify_ticket_valid_unused():
    conn = make_conn(fetchrow_result={
        "id": SAMPLE_TICKET_ID,
        "status": "valid",
        "is_used": False,
    })

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, consume=False, conn=conn)

    assert result["valid"] is True
    assert result["used"] is False
    assert result["status"] == "valid"
    assert result["ticket_id"] == SAMPLE_TICKET_ID
    assert "ready for entry" in result["message"]


@pytest.mark.asyncio
async def test_verify_ticket_invalid_id_format():
    conn = make_conn()
    result = await verify_ticket(booking_id="not-a-valid-uuid", consume=False, conn=conn)

    assert result["valid"] is False
    assert "Invalid ticket ID format" in result["message"]


@pytest.mark.asyncio
async def test_verify_ticket_not_found():
    conn = make_conn(fetchrow_result=None)
    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, consume=False, conn=conn)

    assert result["valid"] is False
    assert result["message"] == "Ticket not found"


@pytest.mark.asyncio
async def test_verify_ticket_already_used():
    conn = make_conn(fetchrow_result={
        "id": SAMPLE_TICKET_ID,
        "status": "used",
        "is_used": True,
    })

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, consume=False, conn=conn)

    assert result["valid"] is False
    assert result["used"] is True
    assert result["status"] == "used"
    assert "already" in result["message"].lower()


@pytest.mark.asyncio
async def test_verify_ticket_cancelled():
    conn = make_conn(fetchrow_result={
        "id": SAMPLE_TICKET_ID,
        "status": "cancelled",
        "is_used": False,
    })

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, consume=False, conn=conn)

    assert result["valid"] is False
    assert result["status"] == "cancelled"
    assert "cancelled" in result["message"]


@pytest.mark.asyncio
async def test_scan_ticket_success_first_time():
    ticket_detail = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "valid",
        "is_used": False,
        "event_title": "Inception (Re-release)",
        "start_time": "2026-11-17 20:00:00+00",
        "venue_name": "PVR Icon",
        "screen_name": "Audi 1",
        "user_name": "Rahul Sharma",
        "user_email": "rahul@example.com",
    }

    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_detail, consumed_row])

    req = TicketScanRequest(qr_data=f"TICKETFLOW:{SAMPLE_BOOKING_ID}")
    result = await scan_ticket(body=req, conn=conn)

    assert result["success"] is True
    assert result["valid"] is True
    assert result["status"] == "used"
    assert result["used"] is True
    assert result["ticket_id"] == SAMPLE_TICKET_ID
    assert result["event"]["title"] == "Inception (Re-release)"
    assert result["attendee"]["name"] == "Rahul Sharma"


@pytest.mark.asyncio
async def test_scan_ticket_rejects_already_used_reusable_attempt():
    ticket_detail = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
        "event_title": "Inception (Re-release)",
        "start_time": "2026-11-17 20:00:00+00",
        "venue_name": "PVR Icon",
        "screen_name": "Audi 1",
        "user_name": "Rahul Sharma",
        "user_email": "rahul@example.com",
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=ticket_detail)

    req = TicketScanRequest(booking_id=SAMPLE_BOOKING_ID)
    with pytest.raises(HTTPException) as exc_info:
        await scan_ticket(body=req, conn=conn)

    assert exc_info.value.status_code == 409
    assert "already been scanned and used" in exc_info.value.detail
    assert "Duplicate entry is not permitted" in exc_info.value.detail


@pytest.mark.asyncio
async def test_scan_ticket_rejects_cancelled_ticket():
    ticket_detail = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "cancelled",
        "is_used": False,
        "event_title": "Inception (Re-release)",
        "start_time": "2026-11-17 20:00:00+00",
        "venue_name": "PVR Icon",
        "screen_name": "Audi 1",
        "user_name": "Rahul Sharma",
        "user_email": "rahul@example.com",
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=ticket_detail)

    req = TicketScanRequest(booking_id=SAMPLE_BOOKING_ID)
    with pytest.raises(HTTPException) as exc_info:
        await scan_ticket(body=req, conn=conn)

    assert exc_info.value.status_code == 400
    assert "cancelled" in exc_info.value.detail


@pytest.mark.asyncio
async def test_scan_ticket_by_booking_id_endpoint():
    ticket_detail = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "valid",
        "is_used": False,
        "event_title": "Interstellar",
        "start_time": "2026-11-17 21:00:00+00",
        "venue_name": "PVR Grand",
        "screen_name": "Audi 2",
        "user_name": "Pooja Patel",
        "user_email": "pooja@example.com",
    }
    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_detail, consumed_row])

    result = await scan_ticket_by_booking_id(booking_id=SAMPLE_BOOKING_ID, conn=conn)
    assert result["success"] is True
    assert result["used"] is True
    assert result["status"] == "used"


@pytest.mark.asyncio
async def test_verify_with_consume_flag_marks_used():
    ticket_detail = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "valid",
        "is_used": False,
        "event_title": "Interstellar",
        "start_time": "2026-11-17 21:00:00+00",
        "venue_name": "PVR Grand",
        "screen_name": "Audi 2",
        "user_name": "Pooja Patel",
        "user_email": "pooja@example.com",
    }
    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_detail, consumed_row])

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, consume=True, conn=conn)
    assert result["success"] is True
    assert result["used"] is True
    assert result["status"] == "used"
