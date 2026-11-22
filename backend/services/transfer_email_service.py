"""Emails for ticket transfers: "you've been sent tickets" and "your transfer was answered"."""
import asyncio
import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import FRONTEND_URL, GMAIL_APP_PASSWORD, GMAIL_USER
from services.ticket_service import format_show_datetime

SMTP_TIMEOUT_SECONDS = 20


def _page(title: str, body: str) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1a1a2e;color:white;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;">🎫 TicketFlow</h1>
        <p style="margin:4px 0 0;">{html.escape(title)}</p>
      </div>
      <div style="padding:24px;background:#f9f9f9;">{body}</div>
      <div style="background:#0f3460;color:#aaa;padding:10px;text-align:center;
                  font-size:12px;border-radius:0 0 8px 8px;">
        TicketFlow — DA-IICT IT314 SWE Project
      </div>
    </body></html>"""


def _show_line(transfer: dict) -> str:
    when = format_show_datetime(transfer.get("start_time")) if transfer.get("start_time") else ""
    where = ", ".join(p for p in (transfer.get("venue_name"), transfer.get("city")) if p)
    return " · ".join(html.escape(p) for p in (when, where) if p)


def build_received_email(transfer: dict) -> tuple[str, str]:
    """(subject, html) for the person who was sent tickets."""
    sender = html.escape(transfer["sender_name"])
    event = html.escape(transfer["event_title"])
    seats = html.escape(", ".join(transfer["seats"]))
    link = f"{FRONTEND_URL.rstrip('/')}/tickets/received"
    body = f"""
        <p>Hi {html.escape(transfer['recipient_name'])},</p>
        <p><strong>{sender}</strong> sent you tickets for <strong>{event}</strong>.</p>
        <p>{_show_line(transfer)}<br>Seats: <strong>{seats}</strong></p>
        <p>Accept them to get your own QR code for entry.</p>
        <p style="margin-top:20px;">
          <a href="{link}" style="background:#3b82f6;color:white;padding:10px 18px;border-radius:6px;
             text-decoration:none;font-weight:600;">View and accept →</a>
        </p>"""
    return f"{transfer['sender_name']} sent you tickets for {transfer['event_title']}", _page("You've been sent tickets", body)


def build_response_email(transfer: dict) -> tuple[str, str]:
    """(subject, html) telling the sender their transfer was accepted or declined."""
    accepted = transfer["status"] == "accepted"
    word = "accepted" if accepted else "declined"
    who = html.escape(transfer["recipient_name"])
    event = html.escape(transfer["event_title"])
    extra = (
        "Those seats now have their own QR code, so your booking's QR no longer admits them."
        if accepted else
        "The seats are back on your booking, and you can send them to someone else."
    )
    link = f"{FRONTEND_URL.rstrip('/')}/bookings/{transfer['booking_id']}"
    body = f"""
        <p>Hi {html.escape(transfer['sender_name'])},</p>
        <p><strong>{who}</strong> {word} the tickets you sent for <strong>{event}</strong>.</p>
        <p>{extra}</p>
        <p style="margin-top:20px;"><a href="{link}" style="color:#3b82f6;font-weight:600;">View your booking →</a></p>"""
    return f"{transfer['recipient_name']} {word} your tickets for {transfer['event_title']}", _page(f"Transfer {word}", body)


def _send_sync(to_email: str, subject: str, body_html: str) -> None:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        return  # email not configured (local dev / tests)
    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, to_email, msg.as_string())


async def _send(to_email: str, subject: str, body_html: str) -> None:
    try:
        await asyncio.get_running_loop().run_in_executor(None, _send_sync, to_email, subject, body_html)
    except Exception as exc:  # email must never break the transfer itself
        print(f"Transfer email failed (non-fatal): {exc}")


async def send_transfer_received_email(transfer: dict) -> None:
    subject, body = build_received_email(transfer)
    await _send(transfer["recipient_email"], subject, body)


async def send_transfer_response_email(transfer: dict) -> None:
    subject, body = build_response_email(transfer)
    await _send(transfer["sender_email"], subject, body)
