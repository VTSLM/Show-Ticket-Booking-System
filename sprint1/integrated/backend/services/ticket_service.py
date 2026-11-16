import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def build_ticket_pdf(ticket_data: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                             topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle("title", parent=styles["Title"],
                                  fontSize=22, textColor=colors.HexColor("#1a1a2e"),
                                  alignment=TA_CENTER, spaceAfter=0.3*cm)
    elements.append(Paragraph("🎫 TicketFlow", title_style))
    elements.append(Paragraph("Your E-Ticket", ParagraphStyle("sub", parent=styles["Normal"],
                                fontSize=12, textColor=colors.grey, alignment=TA_CENTER)))
    elements.append(Spacer(1, 0.5*cm))

    # Event info table
    info_data = [
        ["Event", ticket_data.get("event_title", "")],
        ["Venue", ticket_data.get("venue_name", "") + (f", {ticket_data.get('venue_city','')}" if ticket_data.get("venue_city") else "")],
        ["Screen", ticket_data.get("screen_name", "")],
        ["Date & Time", ticket_data.get("start_time", "")],
        ["Booked By", ticket_data.get("user_name", "")],
        ["Booking ID", ticket_data.get("booking_id", "")[:16] + "..."],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 11*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.5*cm))

    # Seats
    elements.append(Paragraph("Seats", ParagraphStyle("h2", parent=styles["Heading2"],
                                fontSize=12, textColor=colors.HexColor("#0f3460"))))
    seat_rows = [["Row", "Seat #", "Type", "Price"]]
    for s in ticket_data.get("seats", []):
        seat_rows.append([
            s.get("row_label", ""),
            str(s.get("seat_number", "")),
            s.get("seat_type", "standard").capitalize(),
            f"₹{float(s.get('price', 0)):.2f}"
        ])
    seat_rows.append(["", "", "Total", f"₹{float(ticket_data.get('total_amount', 0)):.2f}"])
    seat_table = Table(seat_rows, colWidths=[3*cm, 3*cm, 5*cm, 4*cm])
    seat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e94560")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    elements.append(seat_table)
    elements.append(Spacer(1, 0.5*cm))

    # QR Code
    if ticket_data.get("qr_b64"):
        elements.append(Paragraph("Scan to verify ticket", ParagraphStyle("qr_cap", parent=styles["Normal"],
                                   fontSize=9, textColor=colors.grey, alignment=TA_CENTER)))
        qr_img_data = base64.b64decode(ticket_data["qr_b64"])
        qr_img = Image(io.BytesIO(qr_img_data), width=3.5*cm, height=3.5*cm)
        qr_img.hAlign = "CENTER"
        elements.append(qr_img)

    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph("Thank you for using TicketFlow!", ParagraphStyle("footer", parent=styles["Normal"],
                               fontSize=9, textColor=colors.grey, alignment=TA_CENTER)))

    doc.build(elements)
    return buf.getvalue()
