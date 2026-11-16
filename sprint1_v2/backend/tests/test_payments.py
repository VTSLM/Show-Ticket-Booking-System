import hashlib
import hmac
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from requests.exceptions import Timeout

from routers import payments

BOOKING_ID = "f8fca959-7eb1-4ad1-acc2-c954ad56bcdc"
USER = {"id": "270baccb-3b2a-45ae-a3ad-75aa64426d66"}
ORDER_ID = "order_fixture"
PAYMENT_ID = "pay_fixture"


@pytest.fixture
def checkout(monkeypatch):
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    conn.fetchrow.side_effect = [
        {"status": "pending", "total_amount": Decimal("450.00"), "show_id": "show-1"},
        {"show_terms": None, "event_terms": None},
        {"id": "accepted"},
    ]
    conn.fetchval.return_value = None
    provider = Mock()
    provider.order.create.return_value = {"id": ORDER_ID}
    monkeypatch.setattr(payments, "get_razorpay", lambda: provider)
    return conn, provider


@pytest.mark.asyncio
async def test_checkout_uses_paise_and_persists_order(checkout):
    conn, provider = checkout

    response = await payments.create_order(payments.CreateOrderRequest(booking_id=BOOKING_ID), USER, conn)

    assert response["amount"] == 45000
    assert response["razorpay_order_id"] == ORDER_ID
    assert provider.order.create.call_args.args[0]["amount"] == 45000
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkout_reuses_the_pending_order(checkout):
    conn, provider = checkout
    conn.fetchval.return_value = ORDER_ID

    response = await payments.create_order(payments.CreateOrderRequest(booking_id=BOOKING_ID), USER, conn)

    assert response["razorpay_order_id"] == ORDER_ID
    provider.order.create.assert_not_called()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_zero_price_is_rejected_before_calling_razorpay(checkout):
    conn, provider = checkout
    conn.fetchrow.side_effect = None
    conn.fetchrow.return_value = {"status": "pending", "total_amount": Decimal("0.00")}

    with pytest.raises(HTTPException, match="greater than ₹0") as error:
        await payments.create_order(payments.CreateOrderRequest(booking_id=BOOKING_ID), USER, conn)

    assert error.value.status_code == 400
    provider.order.create.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_error", "status"),
    [(payments.razorpay.errors.BadRequestError("private provider detail"), 502), (Timeout(), 503)],
)
async def test_provider_errors_return_recoverable_responses(checkout, provider_error, status):
    conn, provider = checkout
    provider.order.create.side_effect = provider_error

    with pytest.raises(HTTPException) as error:
        await payments.create_order(payments.CreateOrderRequest(booking_id=BOOKING_ID), USER, conn)

    assert error.value.status_code == status
    assert "private provider detail" not in error.value.detail
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_verification_retry_returns_existing_receipt_without_writes(monkeypatch):
    monkeypatch.setattr(payments, "RAZORPAY_KEY_SECRET", "unit-test-signing-key")
    signature = hmac.new(
        b"unit-test-signing-key", f"{ORDER_ID}|{PAYMENT_ID}".encode(), hashlib.sha256
    ).hexdigest()
    conn = AsyncMock()
    conn.transaction = Mock(return_value=AsyncMock())
    conn.fetchrow.return_value = {"user_id": USER["id"], "status": "confirmed"}
    conn.fetchval.side_effect = ["payment-order-id", "receipt-1"]
    request = payments.VerifyRequest(
        razorpay_order_id=ORDER_ID, razorpay_payment_id=PAYMENT_ID, razorpay_signature=signature,
    )

    result = await payments.verify_payment(BOOKING_ID, request, USER, conn)

    assert result["receipt_number"] == "receipt-1"
    conn.execute.assert_not_awaited()
