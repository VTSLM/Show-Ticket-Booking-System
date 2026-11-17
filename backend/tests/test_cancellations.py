"""Cancelling a booking answers immediately; the Razorpay refund runs afterwards.

The database connection, pool and Razorpay client are fakes; no network is used.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks

from routers import cancellations
from services import refund_service

USER = {"id": "11111111-1111-1111-1111-111111111111"}
BOOKING_ID = "22222222-2222-2222-2222-222222222222"


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


def test_cancel_returns_without_calling_razorpay(monkeypatch):
    refund = AsyncMock()
    monkeypatch.setattr(cancellations, "refund_and_record", refund)
    tasks = BackgroundTasks()

    result = asyncio.run(cancellations.cancel_booking(BOOKING_ID, tasks, USER, _conn(_booking())))

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
    result = asyncio.run(cancellations.cancel_booking(BOOKING_ID, tasks, USER, _conn(row)))

    assert result["refund_initiated"] is False
    assert result["refund_amount"] == 0.0
    assert len(tasks.tasks) == 0


def test_cancel_too_close_to_show_is_refused(monkeypatch):
    from fastapi import HTTPException

    row = _booking(start_time=datetime.now(timezone.utc) + timedelta(minutes=30))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(cancellations.cancel_booking(BOOKING_ID, BackgroundTasks(), USER, _conn(row)))
    assert exc.value.status_code == 400


class _FakeRazorpay:
    calls = []

    def __init__(self, auth):
        self.payment = self

    def refund(self, payment_id, data, **kwargs):
        _FakeRazorpay.calls.append((payment_id, data, kwargs))
        return {"id": "rfnd_TEST"}


def test_refund_call_uses_a_timeout(monkeypatch):
    _FakeRazorpay.calls = []
    monkeypatch.setattr(refund_service.razorpay, "Client", _FakeRazorpay)

    refund_id = asyncio.run(refund_service.initiate_razorpay_refund("pay_TEST123", 21000))

    assert refund_id == "rfnd_TEST"
    payment_id, data, kwargs = _FakeRazorpay.calls[0]
    assert data == {"amount": 21000}
    assert kwargs["timeout"] == refund_service.RAZORPAY_TIMEOUT


def _fake_pool(conn):
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire)
    return pool


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
