import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from routers import cancellations
from services.cancellation_policy_service import (
    evaluate_cancellation_eligibility,
    DEFAULT_POLICY,
)
from services import refund_service


BOOKING_ID = "11111111-2222-3333-4444-555555555555"
SHOW_ID = "22222222-3333-4444-5555-666666666666"
USER_ID = "270baccb-3b2a-45ae-a3ad-75aa64426d66"
OTHER_USER_ID = "99999999-9999-9999-9999-999999999999"
CURRENT_USER = {"id": USER_ID, "email": "customer@example.com", "role": "customer"}
ADMIN_USER = {"id": "admin-id-123", "email": "admin@ticketflow.com", "role": "admin"}


# ----------------------------------------------------------------------
# 1. Unit Tests for Policy & Refund Calculation
# ----------------------------------------------------------------------

def test_policy_service_default_values():
    assert DEFAULT_POLICY["is_refundable"] is True
    assert DEFAULT_POLICY["cutoff_hours"] == 2
    assert DEFAULT_POLICY["deduction_percentage"] == 10.0


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
    # 10% of 1000 = 100, + 50 = 150 charge
    assert breakdown["cancellation_charge"] == 150.0
    assert breakdown["expected_refund"] == 850.0


def test_evaluate_eligibility_cutoff_passed():
    # Only 1 hour until showtime, policy cutoff is 2 hours
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
# 2. Endpoint Tests: Eligibility
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
    # _fetch_booking_for_cancellation does:
    # 1. fetchrow for booking
    # 2. fetch for seats
    # 3. fetchrow for refund
    # get_show_cancellation_policy does:
    # 4. fetchrow for policy
    conn.fetchrow.side_effect = [
        booking_row,
        None,  # refund_row
        DEFAULT_POLICY,  # policy
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
    assert resp["breakdown"]["expected_refund"] == 720.0  # 800 - 10%
    assert resp["breakdown"]["cancellation_charge"] == 80.0


@pytest.mark.asyncio
async def test_get_cancel_eligibility_other_user_403():
    conn = AsyncMock()
    # Booking belongs to OTHER_USER_ID
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
# 3. Endpoint Tests: Cancel Execution & Atomic Transaction
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

    # Sequence of fetchrow calls:
    # 1. _fetch_booking_for_cancellation (booking_row)
    # 2. _fetch_booking_for_cancellation (refund_row) -> None
    # 3. get_show_cancellation_policy -> DEFAULT_POLICY
    # 4. INSERT INTO refunds RETURNING id -> {"id": "refund-uuid-1"}
    conn.fetchrow.side_effect = [
        booking_record,
        None,
        DEFAULT_POLICY,
        {"id": "refund-uuid-1"},
    ]
    conn.fetch.return_value = [
        {"id": "ss-1", "row_label": "B", "seat_number": 5, "seat_type": "standard", "price": Decimal("500.00")},
        {"id": "ss-2", "row_label": "B", "seat_number": 6, "seat_type": "standard", "price": Decimal("500.00")},
    ]

    # Mock Razorpay refund call
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

    # Mock notifications
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
    assert resp["refund_amount"] == 900.0
    assert resp["cancellation_charge"] == 100.0
    assert resp["razorpay_refund_id"] == "rfnd_test_abc123"

    # Verify inventory was released
    conn.execute.assert_any_await(
        """
            UPDATE show_seats
            SET status = 'available',
                locked_by = NULL,
                locked_until = NULL,
                updated_at = now()
            WHERE id = ANY($1::uuid[])
            """,
        ["ss-1", "ss-2"],
    )


@pytest.mark.asyncio
async def test_cancel_booking_duplicate_request_raises_conflict():
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    # Booking already has status 'cancelled'
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
        None,  # refund
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
# 4. Webhook Signature & Event Processing
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

    # Mock signature verification
    monkeypatch.setattr(cancellations, "verify_razorpay_webhook_signature", lambda p, s: True)
    monkeypatch.setattr(cancellations, "create_notification", AsyncMock())
    monkeypatch.setattr(cancellations, "send_refund_status_email", AsyncMock())

    mock_request = Mock()
    mock_request.body = AsyncMock(return_value=raw_body)
    mock_request.headers = {"x-razorpay-signature": "test-sig"}

    res = await cancellations.razorpay_refund_webhook(
        request=mock_request,
        conn=conn,
    )
    assert res["status"] == "success"
    assert res["event"] == "refund.processed"


# ----------------------------------------------------------------------
# 5. Admin Cancellation & Retry Management
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

    res = await cancellations.admin_list_cancellations(
        status="FAILED",
        query="Concert",
        admin_user=ADMIN_USER,
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
    res = await cancellations.admin_retry_refund(
        refund_id="refund-uuid-1",
        req=req,
        admin_user=ADMIN_USER,
        conn=conn,
    )
    assert res["status"] == "success"
    assert res["refund_status"] == "PROCESSED"
    assert res["razorpay_refund_id"] == "rfnd_retry_success"
