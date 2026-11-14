import sys
import zlib
import re
from unittest.mock import MagicMock, patch

sys.path.insert(0, r"d:\Sem 5\Se_project\sprint1_v2\backend")
from services.qr_service import generate_qr_bytes  # noqa: E402
from services.ticket_service import build_ticket_pdf  # noqa: E402
from services import email_service  # noqa: E402

qr = generate_qr_bytes("TICKETFLOW:99999999-9999-9999-9999-999999999991")
data = {
    "ticket_id": "11111111-1111-1111-1111-111111111111",
    "booking_id": "99999999-9999-9999-9999-999999999991",
    "event_title": "Seeded Movie",
    "venue_name": "PVR Ahmedabad",
    "venue_city": "Ahmedabad",
    "screen_name": "Screen 1",
    "start_time": "2026-11-12 18:00:00",
    "seats": [{"row_label": "A", "seat_number": 1, "seat_type": "standard", "price": 500.0}],
    "total_amount": 500.0,
    "user_name": "Alice",
    "user_email": "alice@example.com",
    "qr_b64": qr,
}

pdf_bytes = build_ticket_pdf(data)
# Check compressed PDF streams for literal non-Latin1 replacement / missing glyph markers
streams = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, flags=re.DOTALL)
decompressed = []
for s in streams:
    try:
        decompressed.append(zlib.decompress(s).decode("latin1", errors="replace"))
    except Exception:
        pass
joined = "\n".join(decompressed)
print("PDF byte size:", len(pdf_bytes))
print("Contains 'TicketFlow':", "TicketFlow" in joined)
print("Contains 'Seeded Movie':", "Seeded Movie" in joined)
print("Contains '500.00':", "500.00" in joined)
print("Contains literal '₹' or '\\x80' glyph check:", repr([line for line in joined.splitlines() if "500.00" in line or "TicketFlow" in line]))

# Test email_service._send_email_sync with mocked SMTP_SSL
mock_smtp = MagicMock()
with patch("smtplib.SMTP_SSL") as smtp_cls:
    smtp_cls.return_value.__enter__.return_value = mock_smtp
    email_service._send_email_sync(data)
    assert mock_smtp.login.called
    assert mock_smtp.sendmail.called
    sent_raw = mock_smtp.sendmail.call_args[0][2]
    assert "Your TicketFlow Ticket - Seeded Movie" in sent_raw
    assert 'filename="ticket_99999999.pdf"' in sent_raw
    print("[PASS] TC-TCK-008: email_service composes HTML + PDF attachment and calls SMTP_SSL.sendmail")
