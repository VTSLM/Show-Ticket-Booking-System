from unittest.mock import AsyncMock, MagicMock

import pytest

from services import ticket_transfer as transfers
from services import transfer_demo_payments as demo

TRANSFER = "d8a19e80-1ba8-4d1c-b10d-67432efe34e2"
ROW = {
    "transfer_id": TRANSFER,
    "razorpay_order_id": "order_demo",
    "amount_paise": 100,
    "original_payment_id": "pay_original",
    "recipient_payment_id": None,
    "refund_target": None,
    "refund_id": None,
    "refund_status": None,
}
ITEM = {"id": "pay_friend", "order_id": "order_demo", "status": "captured", "currency": "INR", "amount": 100}


def test_demo_gateway_refuses_live_keys(monkeypatch):
    monkeypatch.setenv("TRANSFER_DEMO_PAYMENTS", "true")
    monkeypatch.setattr(demo, "RAZORPAY_KEY_ID", "rzp_live_example")
    monkeypatch.setattr(demo, "RAZORPAY_KEY_SECRET", "example")
    assert not demo.enabled()


@pytest.mark.asyncio
@pytest.mark.parametrize("item", [{**ITEM, "status": "authorized"}, {**ITEM, "amount": 200}])
async def test_only_matching_captured_payment_can_accept_transfer(monkeypatch, item):
    gateway = AsyncMock(return_value={"items": [item]})
    monkeypatch.setattr(demo, "gateway", gateway)
    conn = MagicMock()
    assert await demo.reconcile(conn, ROW) == "awaiting_payment"
    conn.transaction.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("expired, payment, target", [(False, "pay_original", "buyer"), (True, "pay_friend", "recipient")])
async def test_refund_target_and_idempotency_follow_transfer_result(monkeypatch, expired, payment, target):
    accept = AsyncMock(side_effect=transfers.TransferError(400, "Expired") if expired else None)
    monkeypatch.setattr(transfers, "respond_to_transfer", accept)
    monkeypatch.setattr(transfers, "_load_for_update", AsyncMock(return_value={"to_user_id": "recipient"}))
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=[
        ROW, {**ROW, "recipient_payment_id": ITEM["id"], "refund_target": target, "refund_status": "pending"},
    ])
    conn.execute = AsyncMock()
    gateway = AsyncMock(side_effect=[
        {"items": [ITEM]},
        {"payment_id": payment, "amount": 100, "currency": "INR", "id": "rfnd_demo", "status": "processed"},
    ])
    monkeypatch.setattr(demo, "gateway", gateway)
    assert await demo.reconcile(conn, ROW) == f"{target}_refund_processed"
    accept.assert_awaited_once_with(conn, "recipient", TRANSFER, accept=True, paid_checkout=True)
    assert gateway.await_args.args == ("POST", f"payments/{payment}/refund")
    assert gateway.await_args.kwargs["headers"]["X-Refund-Idempotency"] == f"ticketflow-{TRANSFER}"
    assert conn.execute.await_args.args[1:] == (TRANSFER, "rfnd_demo", "processed")


@pytest.mark.asyncio
async def test_requested_share_cannot_be_accepted_for_free(monkeypatch):
    conn = MagicMock()
    conn.execute = AsyncMock()
    monkeypatch.setattr(
        transfers, "_load_for_update",
        AsyncMock(return_value={"to_user_id": "friend", "status": "pending", "requested_share_paise": 100}),
    )
    with pytest.raises(transfers.TransferError, match="demo checkout"):
        await transfers.respond_to_transfer(conn, "friend", TRANSFER, accept=True)


@pytest.mark.asyncio
async def test_free_transfer_cannot_open_paid_checkout(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(demo, "enabled", lambda: True)
    monkeypatch.setattr(
        transfers, "_load_for_update",
        AsyncMock(return_value={"to_user_id": "friend", "status": "pending", "requested_share_paise": None}),
    )
    gateway = AsyncMock()
    monkeypatch.setattr(demo, "gateway", gateway)
    with pytest.raises(transfers.TransferError, match="sender did not request"):
        await demo.open_checkout(conn, TRANSFER, "friend")
    gateway.assert_not_awaited()
