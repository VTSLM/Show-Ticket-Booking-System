import base64
import io
import uuid
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from routers import tickets as tickets_router
from services import email_service
from services.qr_service import generate_qr_bytes
from services.ticket_service import build_ticket_pdf


def test_tck_001_confirm_generates_ticket_and_is_idempotent(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    fake_db.bookings[fake_db.seed_pending_booking_id]["status"] = "confirmed"

    with patch.object(tickets_router, "send_ticket_email", return_value=None):
        r1 = client.post(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/confirm")
        r2 = client.post(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/confirm")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["ticket_id"] == r2.json()["ticket_id"]
    assert r2.json()["message"] == "Ticket already generated"


def test_tck_002_reject_confirm_for_unpaid_booking(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    res = client.post(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/confirm")
    assert res.status_code == 400
    assert "Payment not completed yet" in res.json()["detail"]


def test_tck_003_qr_service_produces_valid_png():
    b64 = generate_qr_bytes("TICKETFLOW:99999999-9999-9999-9999-999999999991")
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert img.format == "PNG"
    assert img.size[0] > 50 and img.size[1] > 50


def test_tck_004_pdf_service_full_and_minimal_inputs():
    qr_b64 = generate_qr_bytes("TICKETFLOW:test")
    full_pdf = build_ticket_pdf({
        "event_title": "Seeded Movie",
        "venue_name": "PVR Ahmedabad",
        "venue_city": "Ahmedabad",
        "screen_name": "Screen 1",
        "start_time": "2026-11-12 18:00:00",
        "user_name": "Alice",
        "booking_id": "99999999-9999-9999-9999-999999999991",
        "seats": [{"row_label": "A", "seat_number": 1, "seat_type": "standard", "price": 500.0}],
        "total_amount": 500.0,
        "qr_b64": qr_b64,
    })
    minimal_pdf = build_ticket_pdf({"event_title": "Minimal", "booking_id": "12345678", "seats": [], "qr_b64": None})
    assert full_pdf.startswith(b"%PDF-")
    assert minimal_pdf.startswith(b"%PDF-")


def test_tck_005_download_confirmed_ticket_pdf_streams_attachment(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    fake_db.bookings[fake_db.seed_pending_booking_id]["status"] = "confirmed"

    res = client.get(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert f'ticket_{fake_db.seed_pending_booking_id[:8]}.pdf' in res.headers["content-disposition"]
    assert res.content.startswith(b"%PDF-")


def test_tck_006_email_composition_and_non_fatal_smtp_handling(client, fake_db, active_user):
    mock_smtp = MagicMock()
    with patch("smtplib.SMTP_SSL") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = mock_smtp
        email_service._send_email_sync({
            "booking_id": fake_db.seed_pending_booking_id,
            "event_title": "Seeded Movie",
            "venue_name": "PVR Ahmedabad",
            "venue_city": "Ahmedabad",
            "screen_name": "Screen 1",
            "start_time": "2026-11-12 18:00:00",
            "seats": [{"row_label": "A", "seat_number": 1, "seat_type": "standard", "price": 500.0}],
            "total_amount": 500.0,
            "user_name": "Alice",
            "user_email": "alice@example.com",
            "qr_b64": generate_qr_bytes("TICKETFLOW:test"),
        })
    assert mock_smtp.sendmail.called

    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    fake_db.bookings[fake_db.seed_pending_booking_id]["status"] = "confirmed"
    with patch.object(tickets_router, "send_ticket_email", side_effect=RuntimeError("SMTP down")):
        res = client.post(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/confirm")
    assert res.status_code == 200
    assert "ticket_id" in res.json()


def test_tck_007_verify_ticket_unused_used_and_missing(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    fake_db.bookings[fake_db.seed_pending_booking_id]["status"] = "confirmed"

    with patch.object(tickets_router, "send_ticket_email", return_value=None):
        tid = client.post(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/confirm").json()["ticket_id"]

    r_unused = client.get(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/verify")
    assert r_unused.status_code == 200 and r_unused.json()["valid"] is True

    fake_db.tickets[tid]["is_used"] = True
    r_used = client.get(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/verify")
    assert r_used.status_code == 200 and r_used.json()["valid"] is False

    r_missing = client.get(f"/api/tickets/bookings/{uuid.uuid4()}/verify")
    assert r_missing.status_code == 200 and r_missing.json()["valid"] is False


@pytest.mark.xfail(reason="Known defect DEF-TCK-01: GET /pdf allows downloading QR ticket for unpaid pending bookings", strict=True)
def test_tck_008_block_pdf_download_for_unpaid_booking(client, fake_db, active_user):
    active_user.update({"id": fake_db.user_a, "roles": ["customer"]})
    res = client.get(f"/api/tickets/bookings/{fake_db.seed_pending_booking_id}/pdf")
    assert res.status_code in (400, 403)


@pytest.mark.xfail(reason="Known defect DEF-TCK-02: /verify passes malformed booking_id directly into Postgres UUID query", strict=True)
def test_tck_009_verify_malformed_uuid_returns_invalid_json(client):
    res = client.get("/api/tickets/bookings/not-a-uuid/verify")
    assert res.status_code == 200
    assert res.json()["valid"] is False

