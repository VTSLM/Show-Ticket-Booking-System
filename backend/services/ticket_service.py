import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from services.qr_service import generate_qr_bytes


def build_ticket_pdf(payload: dict) -> bytes:
    """
    Build a styled PDF ticket from the confirmed booking payload.
    Returns raw PDF bytes.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # ── Background ──────────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#0D0D0F"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # ── Header bar ──────────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#2563EB"))  # blue accent
    c.rect(0, height - 60 * mm, width, 60 * mm, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 25 * mm, "🎟  TICKETFLOW")

    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#BFDBFE"))
    c.drawCentredString(width / 2, height - 38 * mm, "Your Booking Confirmation")

    # ── Event name ──────────────────────────────────────────────────────────
    event = payload["event"]
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 75 * mm, event["name"])

    # ── Divider ─────────────────────────────────────────────────────────────
    c.setStrokeColor(colors.HexColor("#2563EB"))
    c.setLineWidth(1.5)
    c.line(20 * mm, height - 82 * mm, width - 20 * mm, height - 82 * mm)

    # ── Event details grid ──────────────────────────────────────────────────
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#94A3B8"))

    left_x = 25 * mm
    right_x = width / 2 + 10 * mm
    row1_y = height - 95 * mm
    row2_y = height - 108 * mm

    def label_value(x, y, label, value):
        c.setFillColor(colors.HexColor("#94A3B8"))
        c.setFont("Helvetica", 9)
        c.drawString(x, y + 5 * mm, label.upper())
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, value)

    label_value(left_x, row1_y, "Date", event["date"])
    label_value(right_x, row1_y, "Time", event["time"])
    label_value(left_x, row2_y, "Venue", event["venue"])
    label_value(right_x, row2_y, "Booking ID", payload["booking_id"])

    # ── Seat details ────────────────────────────────────────────────────────
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setFillColor(colors.HexColor("#1E293B"))
    seats_box_y = height - 145 * mm
    c.roundRect(20 * mm, seats_box_y, width - 40 * mm, 28 * mm, 5, fill=1, stroke=0)

    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawString(25 * mm, seats_box_y + 21 * mm, "SEAT(S)")

    seat_text = "  |  ".join(
        [f"Row {s['row']} · Seat {s['number']}  ({s['tier']})  ₹{s['price']}"
         for s in payload["seats"]]
    )
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(25 * mm, seats_box_y + 12 * mm, seat_text)

    c.setFillColor(colors.HexColor("#2563EB"))
    c.setFont("Helvetica-Bold", 13)
    c.drawRightString(width - 25 * mm, seats_box_y + 12 * mm,
                      f"Total: ₹{payload['total_amount']}")

    # ── QR Code ─────────────────────────────────────────────────────────────
    qr_bytes = generate_qr_bytes(payload["booking_id"])
    qr_img = ImageReader(io.BytesIO(qr_bytes))
    qr_size = 45 * mm
    qr_x = (width - qr_size) / 2
    qr_y = height - 210 * mm

    # white bg behind QR
    c.setFillColor(colors.white)
    c.roundRect(qr_x - 4 * mm, qr_y - 4 * mm, qr_size + 8 * mm, qr_size + 8 * mm,
                4, fill=1, stroke=0)
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)

    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, qr_y - 8 * mm, "Scan at entry · One scan per ticket")

    # ── Footer ───────────────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#1E293B"))
    c.rect(0, 0, width, 22 * mm, fill=1, stroke=0)

    user = payload["user"]
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, 14 * mm, f"Ticket for: {user['name']}  ·  {user['email']}")
    c.drawCentredString(width / 2, 8 * mm, f"Transaction ID: {payload['transaction_id']}  ·  Booked: {payload['booked_at'][:10]}")

    c.save()
    buffer.seek(0)
    return buffer.read()
