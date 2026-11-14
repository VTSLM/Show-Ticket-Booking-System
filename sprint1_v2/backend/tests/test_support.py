import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from pydantic import ValidationError

from routers.support import (
    CreateSupportRequest,
    AddMessage,
    create_request,
    list_my_requests,
    get_my_request,
    add_my_message,
    reopen_my_request,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
BOOKING_ID = "33333333-3333-3333-3333-333333333333"
REQUEST_ID = "44444444-4444-4444-4444-444444444444"


def make_user(user_id=USER_ID):
    return {
        "id": user_id,
        "name": "Test User",
        "email": "test@example.com",
    }


def create_mock_connection():
    """
    Creates an asyncpg-like mocked connection.

    The router uses:

        async with conn.transaction():

    so the transaction mock needs explicit async context-manager methods.
    """
    conn = MagicMock()

    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()

    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=None)

    conn.transaction.return_value = transaction

    return conn


def make_request_row(
    request_id=REQUEST_ID,
    user_id=USER_ID,
    status="open",
    category="booking",
):
    return {
        "id": request_id,
        "request_number": "SR-20261113-ABC123",
        "user_id": user_id,
        "booking_id": BOOKING_ID,
        "category": category,
        "subject": "Booking problem",
        "status": status,
        "priority": "normal",
        "created_at": "2026-11-13T10:00:00",
        "updated_at": "2026-11-13T10:00:00",
        "resolved_at": None,
        "booking_number": "BK-1001",
    }


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------

def test_create_support_request_accepts_valid_data():
    request = CreateSupportRequest(
        category="booking",
        subject="Booking problem",
        message="I am unable to access my booking.",
        booking_id=BOOKING_ID,
    )

    assert request.category == "booking"
    assert request.subject == "Booking problem"
    assert request.message == "I am unable to access my booking."
    assert request.booking_id == BOOKING_ID


def test_create_support_request_rejects_short_subject():
    with pytest.raises(ValidationError):
        CreateSupportRequest(
            category="other",
            subject="Help",
            message="This is a valid support message.",
        )


def test_create_support_request_rejects_short_message():
    with pytest.raises(ValidationError):
        CreateSupportRequest(
            category="other",
            subject="Something went wrong",
            message="Too short",
        )


def test_create_support_request_rejects_invalid_booking_uuid():
    with pytest.raises(ValidationError):
        CreateSupportRequest(
            category="booking",
            subject="Booking problem",
            message="I cannot access my booking.",
            booking_id="not-a-valid-uuid",
        )


def test_create_support_request_strips_subject_and_message():
    request = CreateSupportRequest(
        category="other",
        subject="   Payment problem   ",
        message="   Something went wrong with my payment.   ",
    )

    assert request.subject == "Payment problem"
    assert request.message == "Something went wrong with my payment."


def test_add_message_rejects_empty_message():
    with pytest.raises(ValidationError):
        AddMessage(message="   ")


# ---------------------------------------------------------------------------
# Create request tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_payment_request_gets_high_priority():
    conn = create_mock_connection()

    conn.fetchrow.return_value = {
        "id": REQUEST_ID,
        "request_number": "SR-20261113-ABC123",
        "status": "open",
        "priority": "high",
        "created_at": "2026-11-13T10:00:00",
    }

    request = CreateSupportRequest(
        category="payment",
        subject="Payment failed",
        message="My payment was deducted but booking failed.",
    )

    result = await create_request(
        req=request,
        current_user=make_user(),
        conn=conn,
    )

    assert result["priority"] == "high"
    assert result["status"] == "open"

    # Initial customer message must be inserted.
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_refund_request_gets_high_priority():
    conn = create_mock_connection()

    conn.fetchrow.return_value = {
        "id": REQUEST_ID,
        "request_number": "SR-20261113-ABC123",
        "status": "open",
        "priority": "high",
        "created_at": "2026-11-13T10:00:00",
    }

    request = CreateSupportRequest(
        category="refund",
        subject="Refund not received",
        message="I requested a refund but have not received it.",
        booking_id=BOOKING_ID,
    )

    conn.fetchval.return_value = 1

    result = await create_request(
        req=request,
        current_user=make_user(),
        conn=conn,
    )

    assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_create_booking_request_requires_booking():
    conn = create_mock_connection()

    request = CreateSupportRequest(
        category="booking",
        subject="Booking problem",
        message="I am unable to access my booking.",
    )

    with pytest.raises(HTTPException) as exc:
        await create_request(
            req=request,
            current_user=make_user(),
            conn=conn,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Please select the booking this is about"

    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_refund_request_requires_booking():
    conn = create_mock_connection()

    request = CreateSupportRequest(
        category="refund",
        subject="Refund problem",
        message="I need help with my refund.",
    )

    with pytest.raises(HTTPException) as exc:
        await create_request(
            req=request,
            current_user=make_user(),
            conn=conn,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Please select the booking this is about"


@pytest.mark.asyncio
async def test_create_request_rejects_booking_owned_by_another_user():
    conn = create_mock_connection()

    # Booking ownership check returns nothing.
    conn.fetchval.return_value = None

    request = CreateSupportRequest(
        category="booking",
        subject="Booking problem",
        message="I cannot access this booking.",
        booking_id=BOOKING_ID,
    )

    with pytest.raises(HTTPException) as exc:
        await create_request(
            req=request,
            current_user=make_user(USER_ID),
            conn=conn,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Booking not found"


@pytest.mark.asyncio
async def test_create_request_with_owned_booking_succeeds():
    conn = create_mock_connection()

    conn.fetchval.return_value = 1

    conn.fetchrow.return_value = {
        "id": REQUEST_ID,
        "request_number": "SR-20261113-ABC123",
        "status": "open",
        "priority": "normal",
        "created_at": "2026-11-13T10:00:00",
    }

    request = CreateSupportRequest(
        category="booking",
        subject="Booking problem",
        message="I cannot access my booking.",
        booking_id=BOOKING_ID,
    )

    result = await create_request(
        req=request,
        current_user=make_user(),
        conn=conn,
    )

    assert result["status"] == "open"
    assert result["request_number"] == "SR-20261113-ABC123"

    conn.fetchval.assert_awaited_once()
    conn.fetchrow.assert_awaited_once()
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_account_request_does_not_require_booking():
    conn = create_mock_connection()

    conn.fetchrow.return_value = {
        "id": REQUEST_ID,
        "request_number": "SR-20261113-ABC123",
        "status": "open",
        "priority": "normal",
        "created_at": "2026-11-13T10:00:00",
    }

    request = CreateSupportRequest(
        category="account",
        subject="Cannot login",
        message="I am unable to log into my account.",
    )

    result = await create_request(
        req=request,
        current_user=make_user(),
        conn=conn,
    )

    assert result["status"] == "open"

    # No booking ownership query should be required.
    conn.fetchval.assert_not_awaited()


# ---------------------------------------------------------------------------
# List requests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_my_requests_returns_only_user_requests():
    conn = create_mock_connection()

    conn.fetch.return_value = [
        {
            "id": REQUEST_ID,
            "request_number": "SR-20261113-ABC123",
            "category": "booking",
            "subject": "Booking problem",
            "status": "open",
            "priority": "normal",
            "created_at": "2026-11-13T10:00:00",
            "updated_at": "2026-11-13T10:00:00",
            "booking_number": "BK-1001",
            "message_count": 1,
            "last_reply_by_admin": False,
        }
    ]

    result = await list_my_requests(
        current_user=make_user(USER_ID),
        conn=conn,
        status=None,
    )

    assert len(result) == 1
    assert result[0]["request_number"] == "SR-20261113-ABC123"

    conn.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_my_requests_passes_status_filter():
    conn = create_mock_connection()

    conn.fetch.return_value = []

    result = await list_my_requests(
        current_user=make_user(USER_ID),
        conn=conn,
        status="resolved",
    )

    assert result == []

    args = conn.fetch.await_args.args

    # The user ID and status should be supplied to the query.
    assert USER_ID in args
    assert "resolved" in args


# ---------------------------------------------------------------------------
# Get request / ownership tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_my_request_returns_request_and_messages():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row()

    conn.fetch.return_value = [
        {
            "id": "55555555-5555-5555-5555-555555555555",
            "message": "I am having a booking problem.",
            "is_admin": False,
            "created_at": "2026-11-13T10:00:00",
            "sender_name": "Test User",
        },
        {
            "id": "66666666-6666-6666-6666-666666666666",
            "message": "We are looking into this.",
            "is_admin": True,
            "created_at": "2026-11-13T10:05:00",
            "sender_name": "TicketFlow Support",
        },
    ]

    result = await get_my_request(
        request_id=REQUEST_ID,
        current_user=make_user(),
        conn=conn,
    )

    assert result["id"] == REQUEST_ID
    assert len(result["messages"]) == 2
    assert result["messages"][0]["is_admin"] is False
    assert result["messages"][1]["is_admin"] is True


@pytest.mark.asyncio
async def test_get_my_request_rejects_request_belonging_to_another_user():
    conn = create_mock_connection()

    conn.fetchrow.return_value = None

    with pytest.raises(HTTPException) as exc:
        await get_my_request(
            request_id=REQUEST_ID,
            current_user=make_user(USER_ID),
            conn=conn,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Support request not found"


# ---------------------------------------------------------------------------
# Customer reply tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_can_reply_to_open_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row(status="open")

    conn.fetchrow.side_effect = [
        make_request_row(status="open"),
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "message": "Here is some additional information.",
            "is_admin": False,
            "created_at": "2026-11-13T10:10:00",
        },
    ]

    body = AddMessage(
        message="  Here is some additional information.  "
    )

    result = await add_my_message(
        request_id=REQUEST_ID,
        body=body,
        current_user=make_user(),
        conn=conn,
    )

    assert result["message"] == "Here is some additional information."
    assert result["is_admin"] is False
    assert result["sender_name"] == "Test User"

    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_customer_cannot_reply_to_resolved_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row(
        status="resolved"
    )

    body = AddMessage(
        message="I still have a problem."
    )

    with pytest.raises(HTTPException) as exc:
        await add_my_message(
            request_id=REQUEST_ID,
            body=body,
            current_user=make_user(),
            conn=conn,
        )

    assert exc.value.status_code == 400
    assert (
        exc.value.detail
        == "This request is resolved. Reopen it to send a new message."
    )

    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_customer_cannot_reply_to_closed_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row(
        status="closed"
    )

    body = AddMessage(
        message="I still have a problem."
    )

    with pytest.raises(HTTPException) as exc:
        await add_my_message(
            request_id=REQUEST_ID,
            body=body,
            current_user=make_user(),
            conn=conn,
        )

    assert exc.value.status_code == 400

    conn.execute.assert_not_awaited()


# ---------------------------------------------------------------------------
# Reopen tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_can_reopen_resolved_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row(
        status="resolved"
    )

    body = AddMessage(
        message="The issue is still not fixed."
    )

    result = await reopen_my_request(
        request_id=REQUEST_ID,
        body=body,
        current_user=make_user(),
        conn=conn,
    )

    assert result["id"] == REQUEST_ID
    assert result["status"] == "open"

    # Two database operations:
    # 1. Update request
    # 2. Insert reopen message
    assert conn.execute.await_count == 2


@pytest.mark.asyncio
async def test_customer_cannot_reopen_open_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row(
        status="open"
    )

    body = AddMessage(
        message="Please reopen this."
    )

    with pytest.raises(HTTPException) as exc:
        await reopen_my_request(
            request_id=REQUEST_ID,
            body=body,
            current_user=make_user(),
            conn=conn,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Only resolved requests can be reopened"

    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_customer_cannot_reopen_closed_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request_row(
        status="closed"
    )

    body = AddMessage(
        message="Please reopen this."
    )

    with pytest.raises(HTTPException) as exc:
        await reopen_my_request(
            request_id=REQUEST_ID,
            body=body,
            current_user=make_user(),
            conn=conn,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Only resolved requests can be reopened"

    conn.execute.assert_not_awaited()