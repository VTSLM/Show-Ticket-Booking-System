import os
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def send_ticket_email(user_email: str, user_name: str, event_name: str,
                      booking_id: str, pdf_bytes: bytes) -> bool:
    """
    Send booking confirmation email with PDF ticket via Gmail SMTP.
    Requires GMAIL_USER and GMAIL_APP_PASSWORD in .env
    """
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        print("[EMAIL] GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
        return False

    # ── Build the email ──────────────────────────────────────────────────────
    msg = MIMEMultipart("mixed")
    msg["From"] = f"TicketFlow <{gmail_user}>"
    msg["To"] = user_email
    msg["Subject"] = f"Your Ticket for {event_name} 🎟"

    html_body = f"""
    <div style="font-family:sans-serif;background:#0D0D0F;color:#fff;
                padding:32px;border-radius:12px;max-width:600px;margin:auto">
      <h1 style="color:#2563EB;margin-bottom:4px">🎟 TicketFlow</h1>
      <p style="color:#94A3B8;margin-top:0">Booking Confirmation</p>
      <hr style="border-color:#1E293B"/>
      <h2 style="color:#fff">{event_name}</h2>
      <p style="color:#BFDBFE">
        Hi {user_name},<br/><br/>
        Your booking is confirmed! Your ticket is attached as a PDF.<br/>
        Please carry it (digital or printed) to the venue for entry scanning.
      </p>
      <p style="background:#1E293B;padding:12px 16px;border-radius:8px;
                font-family:monospace;color:#60A5FA">
        Booking ID: {booking_id}
      </p>
      <p style="color:#64748B;font-size:12px;margin-top:24px">
        Questions? Reply to this email.<br/>
        © 2026 TicketFlow · IT314 Project · DA-IICT
      </p>
    </div>
    """

    msg.attach(MIMEText(html_body, "html"))

    # ── Attach PDF ───────────────────────────────────────────────────────────
    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="ticket_{booking_id}.pdf"'
    )
    msg.attach(attachment)

    # ── Send via Gmail SMTP ──────────────────────────────────────────────────
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, user_email, msg.as_string())
        print(f"[EMAIL] ✅ Ticket sent to {user_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[EMAIL ERROR] Authentication failed — check GMAIL_APP_PASSWORD in .env")
        return False
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False
