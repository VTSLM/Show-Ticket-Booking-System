import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from routers.support_admin import (
    AdminReplyBody,
    StatusChangeBody,
    list_all_requests,
    get_request_detail,
    admin_reply,
    change_status,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUEST_ID = "44444444-4444-4444-4444-444444444444"
ADMIN_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_ID = "11111111-1111-1111-1111-111111111111"


def make_admin():
    return {
        "id": ADMIN_ID,
        "name": "Test Admin",
        "email": "admin@example.com",
    }


def create_mock_connection():
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


def make_request(
    status="open",
    request_id=REQUEST_ID,
):
    return {
        "id": request_id,
        "request_number": "SR-20261113-ABC123",
        "user_id": USER_ID,
        "booking_id": None,
        "category": "payment",
        "subject": "Payment problem",
        "status": status,
        "priority": "high",
        "created_at": datetime(2026, 11, 13, 10, 0, 0),
        "updated_at": datetime(2026, 11, 13, 10, 0, 0),
        "resolved_at": None,
        "user_name": "Test User",
        "user_email": "test@example.com",
        "booking_number": None,
    }


# ---------------------------------------------------------------------------
# Request body validation
# ---------------------------------------------------------------------------

def test_admin_reply_body_accepts_valid_message():
    body = AdminReplyBody(
        message="We have checked your payment.",
        status="in_progress",
    )

    assert body.message == "We have checked your payment."
    assert body.status == "in_progress"


def test_admin_reply_body_rejects_empty_message():
    with pytest.raises(ValidationError):
        AdminReplyBody(message="")


def test_status_change_body_accepts_valid_status():
    body = StatusChangeBody(status="resolved")

    assert body.status == "resolved"


def test_status_change_body_rejects_invalid_status():
    with pytest.raises(ValidationError):
        StatusChangeBody(status="invalid_status")


# ---------------------------------------------------------------------------
# Admin list tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_list_all_support_requests():
    conn = create_mock_connection()

    conn.fetch.return_value = [
        {
            "id": REQUEST_ID,
            "request_number": "SR-20261113-ABC123",
            "category": "payment",
            "subject": "Payment problem",
            "status": "open",
            "priority": "high",
            "created_at": datetime(2026, 11, 13, 10, 0, 0),
            "updated_at": datetime(2026, 11, 13, 10, 0, 0),
            "user_name": "Test User",
            "user_email": "test@example.com",
            "message_count": 2,
            "last_reply_by_admin": True,
        }
    ]

    result = await list_all_requests(
        status=None,
        category=None,
        search=None,
        admin=make_admin(),
        conn=conn,
    )

    assert len(result) == 1
    assert result[0]["request_number"] == "SR-20261113-ABC123"
    assert result[0]["category"] == "payment"


@pytest.mark.asyncio
async def test_admin_list_can_filter_by_status():
    conn = create_mock_connection()

    conn.fetch.return_value = []

    result = await list_all_requests(
        status="resolved",
        category=None,
        search=None,
        admin=make_admin(),
        conn=conn,
    )

    assert result == []

    args = conn.fetch.await_args.args

    assert "resolved" in args


@pytest.mark.asyncio
async def test_admin_list_can_filter_by_category():
    conn = create_mock_connection()

    conn.fetch.return_value = []

    result = await list_all_requests(
        status=None,
        category="payment",
        search=None,
        admin=make_admin(),
        conn=conn,
    )

    assert result == []

    args = conn.fetch.await_args.args

    assert "payment" in args


@pytest.mark.asyncio
async def test_admin_list_can_search_subject_or_request_number():
    conn = create_mock_connection()

    conn.fetch.return_value = []

    result = await list_all_requests(
        status=None,
        category=None,
        search="payment",
        admin=make_admin(),
        conn=conn,
    )

    assert result == []

    args = conn.fetch.await_args.args

    assert "%payment%" in args


# ---------------------------------------------------------------------------
# Admin request detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_get_request_detail_with_messages():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request()

    conn.fetch.return_value = [
        {
            "id": "55555555-5555-5555-5555-555555555555",
            "message": "I was charged twice.",
            "is_admin": False,
            "created_at": datetime(2026, 11, 13, 10, 0, 0),
            "sender_name": "Test User",
        },
        {
            "id": "66666666-6666-6666-6666-666666666666",
            "message": "We are investigating this.",
            "is_admin": True,
            "created_at": datetime(2026, 11, 13, 10, 5, 0),
            "sender_name": "Test Admin",
        },
    ]

    result = await get_request_detail(
        request_id=REQUEST_ID,
        _=make_admin(),
        conn=conn,
    )

    assert result["id"] == REQUEST_ID
    assert len(result["messages"]) == 2
    assert result["messages"][0]["is_admin"] is False
    assert result["messages"][1]["is_admin"] is True


@pytest.mark.asyncio
async def test_admin_get_request_returns_404_for_unknown_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = None

    with pytest.raises(HTTPException) as exc:
        await get_request_detail(
            request_id=REQUEST_ID,
            _=make_admin(),
            conn=conn,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Support request not found"


# ---------------------------------------------------------------------------
# Admin reply
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_reply_to_open_request():
    conn = create_mock_connection()

    conn.fetchrow.side_effect = [
        make_request(status="open"),
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "message": "We have checked your payment.",
            "is_admin": True,
            "created_at": datetime(2026, 11, 13, 10, 10, 0),
        },
    ]

    body = AdminReplyBody(
        message="  We have checked your payment.  "
    )

    with patch(
        "routers.support_admin.send_admin_reply_notification",
        new=AsyncMock(),
    ) as email_mock:

        result = await admin_reply(
            request_id=REQUEST_ID,
            body=body,
            admin=make_admin(),
            conn=conn,
        )

    assert result["message"] == "We have checked your payment."
    assert result["is_admin"] is True
    assert result["sender_name"] == "Test Admin"
    assert result["new_status"] == "open"

    conn.execute.assert_awaited_once()
    email_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_reply_can_change_status_to_in_progress():
    conn = create_mock_connection()

    conn.fetchrow.side_effect = [
        make_request(status="open"),
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "message": "We are investigating this.",
            "is_admin": True,
            "created_at": datetime(2026, 11, 13, 10, 10, 0),
        },
    ]

    body = AdminReplyBody(
        message="We are investigating this.",
        status="in_progress",
    )

    with patch(
        "routers.support_admin.send_admin_reply_notification",
        new=AsyncMock(),
    ):
        result = await admin_reply(
            request_id=REQUEST_ID,
            body=body,
            admin=make_admin(),
            conn=conn,
        )

    assert result["new_status"] == "in_progress"


@pytest.mark.asyncio
async def test_admin_reply_can_resolve_request():
    conn = create_mock_connection()

    conn.fetchrow.side_effect = [
        make_request(status="in_progress"),
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "message": "The issue has been resolved.",
            "is_admin": True,
            "created_at": datetime(2026, 11, 13, 10, 10, 0),
        },
    ]

    body = AdminReplyBody(
        message="The issue has been resolved.",
        status="resolved",
    )

    with patch(
        "routers.support_admin.send_admin_reply_notification",
        new=AsyncMock(),
    ):
        result = await admin_reply(
            request_id=REQUEST_ID,
            body=body,
            admin=make_admin(),
            conn=conn,
        )

    assert result["new_status"] == "resolved"

    # Verify that resolved_at is set when resolving.
    execute_args = conn.execute.await_args.args

    assert "resolved_at=now()" in execute_args[0]


@pytest.mark.asyncio
async def test_admin_cannot_reply_to_closed_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request(
        status="closed"
    )

    body = AdminReplyBody(
        message="Trying to reply to a closed request."
    )

    with pytest.raises(HTTPException) as exc:
        await admin_reply(
            request_id=REQUEST_ID,
            body=body,
            admin=make_admin(),
            conn=conn,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Cannot reply to a closed request"

    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_reply_email_failure_does_not_fail_request():
    conn = create_mock_connection()

    conn.fetchrow.side_effect = [
        make_request(status="open"),
        {
            "id": "77777777-7777-7777-7777-777777777777",
            "message": "We have checked your issue.",
            "is_admin": True,
            "created_at": datetime(2026, 11, 13, 10, 10, 0),
        },
    ]

    body = AdminReplyBody(
        message="We have checked your issue."
    )

    with patch(
        "routers.support_admin.send_admin_reply_notification",
        new=AsyncMock(
            side_effect=Exception("Email service unavailable")
        ),
    ):
        result = await admin_reply(
            request_id=REQUEST_ID,
            body=body,
            admin=make_admin(),
            conn=conn,
        )

    # Email failure must not cause the API request itself to fail.
    assert result["message"] == "We have checked your issue."
    assert result["new_status"] == "open"


# ---------------------------------------------------------------------------
# Status change
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_change_status_to_in_progress():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request(
        status="open"
    )

    body = StatusChangeBody(
        status="in_progress"
    )

    result = await change_status(
        request_id=REQUEST_ID,
        body=body,
        _=make_admin(),
        conn=conn,
    )

    assert result == {"status": "in_progress"}

    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_can_change_status_to_resolved():
    conn = create_mock_connection()

    conn.fetchrow.return_value = make_request(
        status="in_progress"
    )

    body = StatusChangeBody(
        status="resolved"
    )

    result = await change_status(
        request_id=REQUEST_ID,
        body=body,
        _=make_admin(),
        conn=conn,
    )

    assert result == {"status": "resolved"}

    execute_args = conn.execute.await_args.args

    assert "resolved_at=now()" in execute_args[0]


@pytest.mark.asyncio
async def test_admin_change_status_returns_404_for_unknown_request():
    conn = create_mock_connection()

    conn.fetchrow.return_value = None

    body = StatusChangeBody(
        status="resolved"
    )

    with pytest.raises(HTTPException) as exc:
        await change_status(
            request_id=REQUEST_ID,
            body=body,
            _=make_admin(),
            conn=conn,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Support request not found"

    conn.execute.assert_not_awaited()