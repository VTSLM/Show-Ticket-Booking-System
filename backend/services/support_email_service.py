# services/support_email_service.py
# Customer Care email notifications (Hari, Sprint 2 — item 7)
#
# send_admin_reply_notification  → email customer when admin replies
# send_new_ticket_notification   → email admin when a new ticket is created
#
# Both are async wrappers that run the SMTP call in a thread executor
# so they don't block the event loop.

import smtplib
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import GMAIL_USER, GMAIL_APP_PASSWORD

# ── Admin reply → customer ────────────────────────────────────────────────────

async def send_admin_reply_notification(
    *,
    user_email: str,
    user_name: str,
    subject: str,
    request_number: str,
    admin_message: str,
    new_status: str,
) -> None:
    """Email the customer when the support team replies to their request."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _reply_email_sync,
        user_email, user_name, subject, request_number, admin_message, new_status,
    )


def _reply_email_sync(user_email, user_name, subject, request_number, admin_message, new_status):
    status_color = {
        "open": "#f59e0b", "in_progress": "#3b82f6",
        "resolved": "#10b981", "closed": "#6b7280",
    }.get(new_status, "#6b7280")

    status_label = {
        "open": "Open", "in_progress": "In Progress",
        "resolved": "Resolved", "closed": "Closed",
    }.get(new_status, new_status)

    admin_message_escaped = admin_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1a1a2e;color:white;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;">🎫 TicketFlow Support</h1>
        <p style="margin:4px 0 0;">Our team replied to your request</p>
      </div>
      <div style="padding:24px;background:#f9f9f9;">
        <p>Hi {user_name},</p>
        <p>Our support team has replied to your request <strong>{request_number}</strong>:</p>
        <div style="background:#fff;border-left:4px solid #3b82f6;padding:12px 16px;
                    margin:16px 0;border-radius:4px;white-space:pre-wrap;">{admin_message_escaped}</div>
        <p>
          Status:&nbsp;
          <span style="background:{status_color};color:white;padding:3px 12px;
                       border-radius:12px;font-size:13px;font-weight:600;">
            {status_label}
          </span>
        </p>
        <p style="margin-top:20px;">
          <a href="http://localhost:3000/support" style="color:#3b82f6;font-weight:600;">
            View your request →
          </a>
        </p>
      </div>
      <div style="background:#0f3460;color:#aaa;padding:10px;text-align:center;
                  font-size:12px;border-radius:0 0 8px 8px;">
        TicketFlow — DA-IICT IT314 SWE Project
      </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_USER
    msg["To"] = user_email
    msg["Subject"] = f"[{request_number}] Reply from support: {subject}"
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, user_email, msg.as_string())


# ── New ticket → admin ────────────────────────────────────────────────────────

async def send_new_ticket_notification(
    *,
    admin_email: str,
    user_name: str,
    user_email: str,
    subject: str,
    request_number: str,
    category: str,
    message_preview: str,
) -> None:
    """Email the admin team when a new support ticket is created."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _new_ticket_email_sync,
        admin_email, user_name, user_email, subject, request_number, category, message_preview,
    )


def _new_ticket_email_sync(admin_email, user_name, user_email, subject, request_number, category, message_preview):
    category_label = {
        "payment": "Payment issue", "booking": "Booking issue",
        "refund": "Refund request", "account": "Account / login",
        "other": "Something else",
    }.get(category, category)

    preview = message_preview[:500] + ("…" if len(message_preview) > 500 else "")
    preview_escaped = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#1a1a2e;color:white;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;">🎫 TicketFlow Support</h1>
        <p style="margin:4px 0 0;">New support request</p>
      </div>
      <div style="padding:24px;background:#f9f9f9;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
          <tr><td style="padding:8px;background:#16213e;color:white;font-weight:bold;width:110px;">Request #</td>
              <td style="padding:8px;">{request_number}</td></tr>
          <tr><td style="padding:8px;background:#16213e;color:white;font-weight:bold;">From</td>
              <td style="padding:8px;">{user_name} &lt;{user_email}&gt;</td></tr>
          <tr><td style="padding:8px;background:#16213e;color:white;font-weight:bold;">Category</td>
              <td style="padding:8px;">{category_label}</td></tr>
          <tr><td style="padding:8px;background:#16213e;color:white;font-weight:bold;">Subject</td>
              <td style="padding:8px;">{subject}</td></tr>
        </table>
        <div style="background:#fff;border-left:4px solid #f59e0b;padding:12px 16px;
                    margin:0 0 16px;border-radius:4px;white-space:pre-wrap;">{preview_escaped}</div>
        <p>
          <a href="http://localhost:3000/admin/support" style="color:#3b82f6;font-weight:600;">
            Open in Admin Dashboard →
          </a>
        </p>
      </div>
      <div style="background:#0f3460;color:#aaa;padding:10px;text-align:center;
                  font-size:12px;border-radius:0 0 8px 8px;">
        TicketFlow — DA-IICT IT314 SWE Project
      </div>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_USER
    msg["To"] = admin_email
    msg["Subject"] = f"[New Ticket {request_number}] {subject}"
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_USER, admin_email, msg.as_string())
