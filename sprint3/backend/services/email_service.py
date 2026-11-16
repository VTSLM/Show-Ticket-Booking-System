import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import asyncio
from config import GMAIL_USER, GMAIL_APP_PASSWORD
from services.ticket_service import build_ticket_pdf

async def send_ticket_email(ticket_data: dict):
    """Send ticket confirmation email with PDF attachment."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_email_sync, ticket_data)

def _send_email_sync(ticket_data: dict):
    user_email = ticket_data.get("user_email", "")
    user_name = ticket_data.get("user_name", "Guest")
    event_title = ticket_data.get("event_title", "Event")

    print("EMAIL SERVICE:")
    print("  Sender:", GMAIL_USER)
    print("  Recipient:", user_email)
    print("  Subject:", f"Your TicketFlow Ticket - {event_title}")

    msg = MIMEMultipart("mixed")
    msg["From"] = GMAIL_USER
    msg["To"] = user_email
    msg["Subject"] = f"Your TicketFlow Ticket - {event_title}"

    seats_html = "".join([
        f"<tr><td>{s.get('row_label','')}{s.get('seat_number','')}</td>"
        f"<td>{s.get('seat_type','standard').capitalize()}</td>"
        f"<td>₹{float(s.get('price',0)):.2f}</td></tr>"
        for s in ticket_data.get("seats", [])
    ])

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background:#1a1a2e; color:white; padding:20px; text-align:center; border-radius:8px 8px 0 0;">
        <h1>🎫 TicketFlow</h1><p>Booking Confirmed!</p>
      </div>
      <div style="padding:20px; background:#f9f9f9;">
        <p>Hi {user_name},</p>
        <p>Your booking for <strong>{event_title}</strong> is confirmed.</p>
        <table style="width:100%; border-collapse:collapse; margin:15px 0;">
          <tr><td style="padding:8px; background:#16213e; color:white; font-weight:bold;">Venue</td>
              <td style="padding:8px;">{ticket_data.get('venue_name','')} — {ticket_data.get('venue_city','')}</td></tr>
          <tr><td style="padding:8px; background:#16213e; color:white; font-weight:bold;">Screen</td>
              <td style="padding:8px;">{ticket_data.get('screen_name','')}</td></tr>
          <tr><td style="padding:8px; background:#16213e; color:white; font-weight:bold;">Show Time</td>
              <td style="padding:8px;">{ticket_data.get('start_time','')}</td></tr>
          <tr><td style="padding:8px; background:#16213e; color:white; font-weight:bold;">Total</td>
              <td style="padding:8px;">₹{float(ticket_data.get('total_amount',0)):.2f}</td></tr>
        </table>
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr style="background:#e94560; color:white;">
            <th style="padding:8px;">Seat</th><th style="padding:8px;">Type</th><th style="padding:8px;">Price</th>
          </tr></thead><tbody>{seats_html}</tbody>
        </table>
        <p style="margin-top:20px;">Your PDF ticket is attached. Show it at the venue.</p>
      </div>
      <div style="background:#0f3460; color:#aaa; padding:10px; text-align:center; font-size:12px; border-radius:0 0 8px 8px;">
        TicketFlow — DA-IICT SWE Project
      </div>
    </body></html>"""

    msg.attach(MIMEText(html, "html"))

    # Attach PDF
    try:
        pdf_bytes = build_ticket_pdf(ticket_data)
        pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_part.add_header("Content-Disposition", "attachment",
                            filename=f"ticket_{ticket_data.get('booking_id','')[:8]}.pdf")
        msg.attach(pdf_part)
    except Exception as e:
        print(f"PDF generation for email failed: {e}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
      smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)

      result = smtp.sendmail(
          GMAIL_USER,
          user_email,
          msg.as_string()
      )

      print("SMTP send result:", result)
