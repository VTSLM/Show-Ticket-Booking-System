"""
Tests for Booking Cancellation, Refund Management & Policy Enforcement.
Covers background refund scheduling, timeout handling, policy calculations,
atomic execution, webhook processing, and administrator retry capabilities.
"""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fastapi import BackgroundTasks, HTTPException

from routers import cancellations
from services import refund_service
from services.cancellation_policy_service import (
    DEFAULT_POLICY,
    evaluate_cancellation_eligibility,
)


BOOKING_ID = "11111111-2222-3333-4444-555555555555"
SHOW_ID = "22222222-3333-4444-5555-666666666666"
USER_ID = "270baccb-3b2a-45ae-a3ad-75aa64426d66"
OTHER_USER_ID = "99999999-9999-9999-9999-999999999999"
CURRENT_USER = {"id": USER_ID, "email": "customer@example.com", "role": "customer"}


@pytest.fixture(autouse=True)
def no_ticket_transfers(monkeypatch):
    """These tests' fake connections don't model ticket transfers: assume none exist."""
    monkeypatch.setattr(cancellations, "has_accepted_transfers", AsyncMock(return_value=False))
    monkeypatch.setattr(cancellations, "close_pending_for_booking", AsyncMock())
ADMIN_USER = {"id": "admin-id-123", "email": "admin@ticketflow.com", "role": "admin"}


# ── Helpers for origin/main background tests ─────────────────────────────────

def _conn(booking_row):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=booking_row)
    conn.execute = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


def _booking(**over):
    row = {
        "id": BOOKING_ID,
        "status": "confirmed",
        "total_amount": 210.0,
        "show_id": "33333333-3333-3333-3333-333333333333",
        "start_time": datetime.now(timezone.utc) + timedelta(days=1),
        "payment_id": "44444444-4444-4444-4444-444444444444",
        "payment_status": "successful",
        "transaction_id": "pay_TEST123",
        "paid_amount": 210.0,
    }
    row.update(over)
    return row


class _FakeRazorpay:
    calls = []

    def __init__(self, auth):
        self.payment = self

    def refund(self, payment_id, data, **kwargs):
        _FakeRazorpay.calls.append((payment_id, data, kwargs))
        return {"id": "rfnd_TEST"}


def _fake_pool(conn):
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire)
    return pool


# ----------------------------------------------------------------------
# 1. Background Tasks & Async Refund Tests (from main hardening)
# ----------------------------------------------------------------------

def test_cancel_returns_without_calling_razorpay(monkeypatch):
    refund = AsyncMock()
    monkeypatch.setattr(cancellations, "refund_and_record", refund)
    tasks = BackgroundTasks()

    result = asyncio.run(cancellations.cancel_booking(BOOKING_ID, tasks, CURRENT_USER, _conn(_booking())))

    assert result["status"] == "cancelled"
    assert result["refund_initiated"] is True
    assert result["refund_amount"] == 210.0
    refund.assert_not_awaited()  # nothing slow before the response
    asyncio.run(tasks())
    refund.assert_awaited_once_with("44444444-4444-4444-4444-444444444444", "pay_TEST123", 21000)


def test_cancel_without_payment_schedules_no_refund(monkeypatch):
    refund = AsyncMock()
    monkeypatch.setattr(cancellations, "refund_and_record", refund)
    tasks = BackgroundTasks()

    row = _booking(payment_id=None, transaction_id=None, paid_amount=None)
    result = asyncio.run(cancellations.cancel_booking(BOOKING_ID, tasks, CURRENT_USER, _conn(row)))

    assert result["refund_initiated"] is False
    assert result["refund_amount"] == 0.0
    assert len(tasks.tasks) == 0


def test_cancel_too_close_to_show_is_refused():
    row = _booking(start_time=datetime.now(timezone.utc) + timedelta(minutes=30))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(cancellations.cancel_booking(BOOKING_ID, BackgroundTasks(), CURRENT_USER, _conn(row)))
    assert exc.value.status_code == 400


def test_refund_call_uses_a_timeout(monkeypatch):
    _FakeRazorpay.calls = []
    monkeypatch.setattr(refund_service.razorpay, "Client", _FakeRazorpay)

    refund_id = asyncio.run(refund_service.initiate_razorpay_refund("pay_TEST123", 21000))

    assert refund_id == "rfnd_TEST"
    payment_id, data, kwargs = _FakeRazorpay.calls[0]
    assert data == {"amount": 21000}
    assert kwargs["timeout"] == refund_service.RAZORPAY_TIMEOUT


def test_refund_id_is_stored_after_success(monkeypatch):
    db = MagicMock()
    db.execute = AsyncMock()
    monkeypatch.setattr(refund_service, "initiate_razorpay_refund", AsyncMock(return_value="rfnd_TEST"))
    monkeypatch.setattr(refund_service, "get_pool", AsyncMock(return_value=_fake_pool(db)))

    asyncio.run(refund_service.refund_and_record("pay-row-1", "pay_TEST123", 21000))

    db.execute.assert_awaited_once()
    assert db.execute.await_args.args[1:] == ("rfnd_TEST", "pay-row-1")


def test_refund_failure_is_logged_not_raised(monkeypatch, capsys):
    get_pool = AsyncMock()
    monkeypatch.setattr(refund_service, "initiate_razorpay_refund", AsyncMock(side_effect=TimeoutError("read timed out")))
    monkeypatch.setattr(refund_service, "get_pool", get_pool)

    asyncio.run(refund_service.refund_and_record("pay-row-1", "pay_TEST123", 21000))

    get_pool.assert_not_awaited()
    assert "manual follow-up needed" in capsys.readouterr().out


# ----------------------------------------------------------------------
# 2. Unit Tests for Policy & Refund Calculation
# ----------------------------------------------------------------------

def test_policy_service_default_values():
    assert DEFAULT_POLICY["is_refundable"] is True
    assert DEFAULT_POLICY["cutoff_hours"] == 2
    assert DEFAULT_POLICY["deduction_percentage"] == 0.0


def test_evaluate_eligibility_standard_full_refund():
    future_time = datetime.now(timezone.utc) + timedelta(hours=24)
    booking = {
        "status": "confirmed",
        "start_time": future_time,
        "total_amount": 1000.0,
        "paid_amount": 1000.0,
        "payment_id": "pay-1",
        "payment_status": "successful",
    }
    policy = {
        "name": "Zero Fee Policy",
        "cutoff_hours": 2,
        "deduction_percentage": 0.0,
        "flat_cancellation_fee": 0.0,
        "is_refundable": True,
        "description": "Free cancellation",
    }
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, policy)
    assert eligible is True
    assert reason == ""
    assert breakdown["cancellation_charge"] == 0.0
    assert breakdown["expected_refund"] == 1000.0


def test_evaluate_eligibility_with_percentage_and_flat_fee():
    future_time = datetime.now(timezone.utc) + timedelta(hours=10)
    booking = {
        "status": "confirmed",
        "start_time": future_time,
        "total_amount": 1000.0,
        "paid_amount": 1000.0,
        "payment_id": "pay-1",
        "payment_status": "successful",
    }
    policy = {
        "name": "Standard Fee",
        "cutoff_hours": 2,
        "deduction_percentage": 10.0,
        "flat_cancellation_fee": 50.0,
        "is_refundable": True,
        "description": "10% + 50 fee",
    }
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, policy)
    assert eligible is True
    assert breakdown["cancellation_charge"] == 150.0
    assert breakdown["expected_refund"] == 850.0


def test_evaluate_eligibility_cutoff_passed():
    near_time = datetime.now(timezone.utc) + timedelta(hours=1)
    booking = {
        "status": "confirmed",
        "start_time": near_time,
        "total_amount": 500.0,
        "payment_id": "pay-1",
        "payment_status": "successful",
    }
    policy = dict(DEFAULT_POLICY)
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, policy)
    assert eligible is False
    assert "deadline has passed" in reason.lower()
    assert breakdown == {}


def test_evaluate_eligibility_non_refundable():
    future_time = datetime.now(timezone.utc) + timedelta(hours=48)
    booking = {
        "status": "confirmed",
        "start_time": future_time,
        "total_amount": 800.0,
        "payment_id": "pay-1",
        "payment_status": "successful",
    }
    policy = {
        "name": "Non-Refundable Special",
        "cutoff_hours": 0,
        "deduction_percentage": 100.0,
        "flat_cancellation_fee": 0.0,
        "is_refundable": False,
        "description": "No refunds",
    }
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, policy)
    assert eligible is False
    assert "non-refundable" in reason.lower()


def test_evaluate_eligibility_already_cancelled():
    booking = {
        "status": "cancelled",
        "start_time": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, DEFAULT_POLICY)
    assert eligible is False
    assert "already cancelled" in reason.lower()


def test_evaluate_eligibility_pending_unpaid():
    booking = {
        "status": "pending",
        "start_time": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    eligible, reason, breakdown = evaluate_cancellation_eligibility(booking, DEFAULT_POLICY)
    assert eligible is False
    assert "only confirmed bookings" in reason.lower()


# ----------------------------------------------------------------------
# 3. Endpoint Tests: Eligibility
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_cancel_eligibility_success():
    conn = AsyncMock()
    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    booking_row = {
        "id": BOOKING_ID,
        "show_id": SHOW_ID,
        "user_id": USER_ID,
        "status": "confirmed",
        "total_amount": Decimal("800.00"),
        "created_at": datetime.now(timezone.utc),
        "event_title": "Interstellar Live",
        "poster_url": "https://example.com/poster.jpg",
        "start_time": future_time,
        "venue_name": "IMAX Grand",
        "venue_city": "Mumbai",
        "screen_name": "Screen 1",
        "payment_id": "pay-1",
        "payment_status": "successful",
        "paid_amount": Decimal("800.00"),
        "transaction_id": "pay_rzp_123",
        "razorpay_refund_id": None,
        "refunded_amount": None,
        "refunded_at": None,
        "cancellation_policy_id": None,
        "cancellation_reason": None,
        "cancellation_notes": None,
        "cancellation_charge": None,
        "refund_amount": None,
        "refund_status": None,
        "cancelled_at": None,
        "user_name": "Customer",
        "user_email": "customer@example.com",
    }
    conn.fetchrow.side_effect = [
        booking_row,
        DEFAULT_POLICY,
    ]
    conn.fetch.return_value = [
        {"id": "ss-1", "row_label": "A", "seat_number": 1, "seat_type": "standard", "price": Decimal("400.00")},
        {"id": "ss-2", "row_label": "A", "seat_number": 2, "seat_type": "standard", "price": Decimal("400.00")},
    ]

    resp = await cancellations.check_cancel_eligibility(
        booking_id=BOOKING_ID,
        current_user=CURRENT_USER,
        conn=conn,
    )

    assert resp["eligible"] is True
    assert resp["event_title"] == "Interstellar Live"
    assert resp["seats"] == ["A1", "A2"]
    assert resp["breakdown"]["expected_refund"] == 800.0
    assert resp["breakdown"]["cancellation_charge"] == 0.0


@pytest.mark.asyncio
async def test_get_cancel_eligibility_other_user_403():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": BOOKING_ID,
        "user_id": OTHER_USER_ID,
        "show_id": SHOW_ID,
    }

    with pytest.raises(HTTPException) as exc:
        await cancellations.check_cancel_eligibility(
            booking_id=BOOKING_ID,
            current_user=CURRENT_USER,
            conn=conn,
        )
    assert exc.value.status_code == 403


# ----------------------------------------------------------------------
# 4. Endpoint Tests: Cancel Execution & Atomic Transaction
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_booking_success(monkeypatch):
    conn = AsyncMock()
    mock_tx = AsyncMock()
    conn.transaction = Mock(return_value=mock_tx)

    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    booking_record = {
        "id": BOOKING_ID,
        "user_id": USER_ID,
        "show_id": SHOW_ID,
        "status": "confirmed",
        "total_amount": Decimal("1000.00"),
        "paid_amount": Decimal("1000.00"),
        "start_time": future_time,
        "event_title": "Inception Live",
        "payment_id": "pay-db-id",
        "payment_status": "successful",
        "transaction_id": "pay_rzp_12345",
        "razorpay_refund_id": None,
        "refunded_amount": None,
        "refunded_at": None,
        "cancellation_policy_id": None,
        "cancellation_reason": None,
        "cancellation_notes": None,
        "cancellation_charge": None,
        "refund_amount": None,
        "refund_status": None,
        "cancelled_at": None,
        "venue_name": "Grand Cinema",
        "venue_city": "Mumbai",
        "user_name": "Customer User",
        "user_email": "customer@example.com",
    }

    conn.fetchrow.side_effect = [
        booking_record,
        DEFAULT_POLICY,
    ]
    conn.fetchval = AsyncMock(return_value="refund-uuid-1")
    conn.fetch.return_value = [
        {"id": "ss-1", "row_label": "B", "seat_number": 5, "seat_type": "standard", "price": Decimal("500.00")},
        {"id": "ss-2", "row_label": "B", "seat_number": 6, "seat_type": "standard", "price": Decimal("500.00")},
    ]

    monkeypatch.setattr(
        cancellations,
        "initiate_razorpay_refund",
        AsyncMock(return_value={
            "success": True,
            "refund_id": "rfnd_test_abc123",
            "status": "processed",
            "amount": 900.0,
            "error": None,
        }),
    )

    monkeypatch.setattr(cancellations, "create_notification", AsyncMock())
    monkeypatch.setattr(cancellations, "notify_admins", AsyncMock())
    monkeypatch.setattr(cancellations, "send_cancellation_email", AsyncMock())
    monkeypatch.setattr(cancellations, "send_refund_status_email", AsyncMock())

    req = cancellations.CancelBookingRequest(
        reason="Change of plans",
        comments="Cannot make it this Friday",
    )

    resp = await cancellations.cancel_booking(
        booking_id=BOOKING_ID,
        req=req,
        current_user=CURRENT_USER,
        conn=conn,
    )

    assert resp["status"] == "cancelled"
    assert resp["refund_status"] == "PROCESSED"
    assert resp["refund_amount"] == 1000.0
    assert resp["cancellation_charge"] == 0.0
    assert resp["razorpay_refund_id"] == "rfnd_test_abc123"

    # Verify inventory was released
    assert any("UPDATE show_seats" in str(call) for call in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_cancel_booking_duplicate_request_raises_conflict():
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    conn.fetchrow.side_effect = [
        {
            "id": BOOKING_ID,
            "user_id": USER_ID,
            "show_id": SHOW_ID,
            "status": "cancelled",
            "total_amount": Decimal("1000.00"),
            "start_time": datetime.now(timezone.utc) + timedelta(days=2),
            "venue_name": "Venue",
            "venue_city": "City",
            "event_title": "Title",
            "user_name": "User",
            "user_email": "user@example.com",
            "payment_id": None,
            "cancellation_policy_id": None,
        },
        DEFAULT_POLICY,
    ]
    conn.fetch.return_value = []

    req = cancellations.CancelBookingRequest(reason="Change of plans")
    with pytest.raises(HTTPException) as exc:
        await cancellations.cancel_booking(
            booking_id=BOOKING_ID,
            req=req,
            current_user=CURRENT_USER,
            conn=conn,
        )
    assert exc.value.status_code == 400
    assert "already cancelled" in exc.value.detail.lower()


# ----------------------------------------------------------------------
# 5. Webhook Signature & Event Processing
# ----------------------------------------------------------------------

def test_webhook_signature_verification():
    secret = "test_webhook_secret_key"
    payload = json.dumps({"event": "refund.processed", "payload": {}}).encode("utf-8")
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert refund_service.verify_razorpay_webhook_signature(payload, valid_sig, secret) is True
    assert refund_service.verify_razorpay_webhook_signature(payload, "invalid_sig", secret) is False


@pytest.mark.asyncio
async def test_webhook_refund_processed_event(monkeypatch):
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    conn.fetchrow.return_value = {
        "id": "refund-uuid-1",
        "booking_id": BOOKING_ID,
        "user_id": USER_ID,
        "amount": Decimal("900.00"),
        "customer_email": "user@example.com",
        "event_title": "Concert",
        "booking_number": "TF-12345",
    }

    body = {
        "event": "refund.processed",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_rzp_999",
                    "payment_id": "pay_rzp_888",
                    "status": "processed",
                    "amount": 90000,
                }
            }
        }
    }
    raw_body = json.dumps(body).encode("utf-8")

    monkeypatch.setattr(cancellations, "RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret_key")
    monkeypatch.setattr(cancellations, "verify_razorpay_webhook_signature", lambda b, s, sec: True)
    monkeypatch.setattr(cancellations, "create_notification", AsyncMock())
    monkeypatch.setattr(cancellations, "send_refund_status_email", AsyncMock())

    mock_request = Mock()
    mock_request.body = AsyncMock(return_value=raw_body)

    res = await cancellations.razorpay_refund_webhook(
        request=mock_request,
        x_razorpay_signature="test-sig",
        conn=conn,
    )
    assert res["status"] == "success"
    assert res["event"] == "refund.processed"


# ----------------------------------------------------------------------
# 6. Admin Cancellation & Retry Management
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_list_cancellations():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "booking_id": BOOKING_ID,
            "booking_number": "TF-20261118-ABC123",
            "booking_status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc),
            "customer_name": "Test User",
            "customer_email": "user@example.com",
            "event_title": "Concert",
            "show_time": datetime.now(timezone.utc),
            "venue_name": "Arena",
            "refund_id": "ref-1",
            "refund_status": "FAILED",
            "refund_amount": Decimal("500.00"),
            "cancellation_charge": Decimal("50.00"),
            "cancellation_reason": "Unable to attend",
            "cancellation_notes": None,
            "razorpay_payment_id": "pay_1",
            "razorpay_refund_id": None,
            "failure_reason": "Gateway timeout",
            "retry_count": 1,
            "last_retried_at": None,
        }
    ]

    res = await cancellations.list_admin_cancellations(
        search="Concert",
        refund_status="FAILED",
        current_admin=ADMIN_USER,
        conn=conn,
    )
    assert len(res) == 1
    assert res[0]["refund_status"] == "FAILED"
    assert res[0]["event_title"] == "Concert"


@pytest.mark.asyncio
async def test_admin_retry_refund_success(monkeypatch):
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    conn.fetchrow.return_value = {
        "id": "refund-uuid-1",
        "booking_id": BOOKING_ID,
        "user_id": USER_ID,
        "amount": Decimal("500.00"),
        "razorpay_payment_id": "pay_live_123",
        "customer_email": "customer@example.com",
        "event_title": "Test Show",
        "booking_number": "TF-100",
        "retry_count": 0,
        "status": "FAILED",
    }

    monkeypatch.setattr(
        cancellations,
        "initiate_razorpay_refund",
        AsyncMock(return_value={
            "success": True,
            "refund_id": "rfnd_retry_success",
            "status": "processed",
            "amount": 500.0,
            "error": None,
        }),
    )
    monkeypatch.setattr(cancellations, "create_notification", AsyncMock())
    monkeypatch.setattr(cancellations, "send_refund_status_email", AsyncMock())

    req = cancellations.RetryRefundRequest(notes="Retrying after gateway resolved")
    res = await cancellations.retry_failed_refund(
        refund_id="refund-uuid-1",
        req=req,
        current_admin=ADMIN_USER,
        conn=conn,
    )
    assert res["status"] == "success"
    assert res["refund_status"] == "PROCESSED"
    assert res["razorpay_refund_id"] == "rfnd_retry_success"


# ── Cancel dialog showed "0 Ticket(s)" and "General Admission" for seated bookings ──

def _eligibility_booking_row():
    return {
        "id": BOOKING_ID,
        "show_id": SHOW_ID,
        "user_id": USER_ID,
        "status": "confirmed",
        "total_amount": Decimal("200.00"),
        "created_at": datetime.now(timezone.utc),
        "event_title": "Fixture Movie",
        "poster_url": None,
        "start_time": datetime.now(timezone.utc) + timedelta(days=2),
        "venue_name": "PVR",
        "venue_city": "Vadodara",
        "screen_name": "Screen 1",
        "payment_id": "pay-1",
        "payment_status": "successful",
        "paid_amount": Decimal("200.00"),
        "transaction_id": "pay_rzp_123",
        "razorpay_refund_id": None,
        "refunded_amount": None,
        "refunded_at": None,
        "cancellation_policy_id": None,
        "cancellation_reason": None,
        "cancellation_notes": None,
        "cancellation_charge": None,
        "refund_amount": None,
        "refund_status": None,
        "cancelled_at": None,
        "user_name": "Customer",
        "user_email": "customer@example.com",
    }


@pytest.mark.asyncio
async def test_eligibility_seat_query_uses_real_columns():
    """Row and seat number live on `seats`, and the price column is `unit_price`."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [_eligibility_booking_row(), DEFAULT_POLICY]
    conn.fetch.return_value = [
        {"id": "ss-1", "row_label": "A", "seat_number": 1, "seat_type": "standard", "price": Decimal("200.00")},
    ]
    conn.fetchval.return_value = 0

    resp = await cancellations.check_cancel_eligibility(
        booking_id=BOOKING_ID, current_user=CURRENT_USER, conn=conn,
    )

    sql = conn.fetch.call_args.args[0]
    assert "JOIN seats st ON st.id = ss.seat_id" in sql
    assert "bs.unit_price" in sql
    assert "ss.row_label" not in sql and "bs.price" not in sql
    assert resp["seats"] == ["A1"]
    assert resp["total_seats"] == 1


@pytest.mark.asyncio
async def test_eligibility_counts_standing_passes():
    """A zone (standing) booking has no seats but still has tickets."""
    conn = AsyncMock()
    conn.fetchrow.side_effect = [_eligibility_booking_row(), DEFAULT_POLICY]
    conn.fetch.return_value = []
    conn.fetchval.return_value = 3

    resp = await cancellations.check_cancel_eligibility(
        booking_id=BOOKING_ID, current_user=CURRENT_USER, conn=conn,
    )

    assert resp["seats"] == []
    assert resp["total_seats"] == 3


@pytest.mark.asyncio
async def test_cancel_blocked_when_seats_were_transferred(monkeypatch):
    """A booker can't get a refund for seats a friend has accepted."""
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    booking = {
        "id": BOOKING_ID, "user_id": USER_ID, "show_id": SHOW_ID, "status": "confirmed",
        "total_amount": Decimal("500.00"), "paid_amount": Decimal("500.00"),
        "start_time": datetime.now(timezone.utc) + timedelta(days=2),
        "payment_id": "pay-db-id", "payment_status": "successful", "transaction_id": "pay_rzp_1",
        "refunded_amount": None, "cancelled_at": None,
    }
    conn.fetchrow.side_effect = [booking, DEFAULT_POLICY]
    conn.fetch.return_value = []
    monkeypatch.setattr(cancellations, "has_accepted_transfers", AsyncMock(return_value=True))

    with pytest.raises(HTTPException) as exc:
        await cancellations.cancel_booking(booking_id=BOOKING_ID, current_user=CURRENT_USER, conn=conn)
    assert exc.value.status_code == 400
    assert "transferred" in exc.value.detail
    assert not any("UPDATE bookings" in str(c) for c in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_webhook_keeps_demo_transfer_refunds_separate(monkeypatch):
    monkeypatch.setattr(cancellations, "RAZORPAY_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(cancellations, "verify_razorpay_webhook_signature", lambda *_: True)
    request = Mock()
    request.body = AsyncMock(return_value=json.dumps({
        "event": "refund.processed",
        "payload": {"refund": {"entity": {
            "id": "rfnd_demo", "payment_id": "pay_demo", "receipt": f"tr_{BOOKING_ID}",
            "notes": {"ticketflow_demo_transfer_id": BOOKING_ID},
        }}},
    }).encode())
    conn = AsyncMock()
    result = await cancellations.razorpay_refund_webhook(request, "signature", conn)
    assert result["reason"] == "Transfer demo refund"
    conn.fetchrow.assert_not_awaited()
