import hashlib
import hmac
from unittest.mock import MagicMock, patch
import pytest
from routers import payments as payments_router


def test_pay_001_create_order_converts_amount_to_paise(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    mock_rz = MagicMock()
    mock_rz.order.create.return_value = {"id": "order_Valid001"}

    with patch.object(payments_router, "get_razorpay", return_value=mock_rz):
        res = client.post("/api/payments/orders", json={"booking_id": fake_db.seed_pending_booking_id})

    assert res.status_code == 200
    data = res.json()
    assert data["razorpay_order_id"] == "order_Valid001"
    assert data["amount"] == 50000
    assert data["currency"] == "INR"


def test_pay_002_reject_confirmed_booking_order(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    fake_db.bookings[fake_db.seed_pending_booking_id]["status"] = "confirmed"

    res = client.post("/api/payments/orders", json={"booking_id": fake_db.seed_pending_booking_id})
    assert res.status_code == 400
    assert "cannot pay" in res.json()["detail"].lower()


def test_pay_003_verify_valid_signature_commits_booking_seats_and_receipt(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    order_id = "order_Verify001"
    payment_id = "pay_Verify987654"
    secret = "razorpay_test_secret"
    sig = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    with patch.object(payments_router, "RAZORPAY_KEY_SECRET", secret):
        res = client.post(
            f"/api/payments/orders/{fake_db.seed_pending_booking_id}/verify",
            json={
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": sig,
            },
        )

    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert res.json()["receipt_number"] == f"TF-{fake_db.seed_pending_booking_id[:8].upper()}-987654"
    assert fake_db.bookings[fake_db.seed_pending_booking_id]["status"] == "confirmed"
    assert fake_db.show_seats[fake_db.seed_show_seat_id]["status"] == "booked"
    assert fake_db.show_seats[fake_db.seed_show_seat_id]["locked_by"] is None


def test_pay_004_reject_forged_hmac_signature(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    with patch.object(payments_router, "RAZORPAY_KEY_SECRET", "razorpay_test_secret"):
        res = client.post(
            f"/api/payments/orders/{fake_db.seed_pending_booking_id}/verify",
            json={
                "razorpay_order_id": "order_1",
                "razorpay_payment_id": "pay_1",
                "razorpay_signature": "forged_signature",
            },
        )
    assert res.status_code == 400
    assert res.json()["detail"] == "Invalid payment signature"


@pytest.mark.xfail(reason="Known defect DEF-PAY-03: retry create_order hits uq_one_unresolved_payment_order_per_booking", strict=True)
def test_pay_005_retry_order_after_modal_dismiss(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    mock_rz = MagicMock()
    mock_rz.order.create.side_effect = [{"id": "order_First"}, {"id": "order_Second"}]

    with patch.object(payments_router, "get_razorpay", return_value=mock_rz):
        r1 = client.post("/api/payments/orders", json={"booking_id": fake_db.seed_pending_booking_id})
        r2 = client.post("/api/payments/orders", json={"booking_id": fake_db.seed_pending_booking_id})

    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.xfail(reason="Known defect DEF-PAY-04: int(float(amount) * 100) truncates 19.99 INR to 1998 paise", strict=True)
def test_pay_006_exact_paise_conversion_for_decimal_rupees(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    mock_rz = MagicMock()
    mock_rz.order.create.return_value = {"id": "order_Dec1"}

    with patch.object(payments_router, "get_razorpay", return_value=mock_rz):
        res = client.post("/api/payments/orders", json={"booking_id": fake_db.seed_decimal_booking_id})

    assert res.status_code == 200
    assert res.json()["amount"] == 1999


@pytest.mark.xfail(reason="Known defect DEF-PAY-02: verify_payment lacks booking ownership & order-matching checks", strict=True)
def test_pay_007_block_cross_user_payment_verification(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_b, "roles": ["customer"]})
    secret = "razorpay_test_secret"
    sig = hmac.new(secret.encode(), b"order_Any|pay_Any", hashlib.sha256).hexdigest()

    with patch.object(payments_router, "RAZORPAY_KEY_SECRET", secret):
        res = client.post(
            f"/api/payments/orders/{fake_db.seed_pending_booking_id}/verify",
            json={"razorpay_order_id": "order_Any", "razorpay_payment_id": "pay_Any", "razorpay_signature": sig},
        )
    assert res.status_code in (403, 404)


@pytest.mark.xfail(reason="Known defect DEF-PAY-01: get_receipt queries non-existent receipts.booking_id column", strict=True)
def test_pay_008_fetch_receipt_by_number(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    secret = "razorpay_test_secret"
    sig = hmac.new(secret.encode(), b"order_R1|pay_R123456", hashlib.sha256).hexdigest()

    with patch.object(payments_router, "RAZORPAY_KEY_SECRET", secret):
        verify_res = client.post(
            f"/api/payments/orders/{fake_db.seed_pending_booking_id}/verify",
            json={"razorpay_order_id": "order_R1", "razorpay_payment_id": "pay_R123456", "razorpay_signature": sig},
        )
    receipt_num = verify_res.json()["receipt_number"]
    res = client.get(f"/api/payments/receipts/{receipt_num}")
    assert res.status_code == 200

