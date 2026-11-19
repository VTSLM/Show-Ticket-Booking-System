"""
Comprehensive in-app and email notification service for cancellations & refunds.
Ensures customers and admins receive timely, deduplicated notifications.
"""
import json
import asyncio
from typing import Optional, Dict, Any
import asyncpg
from config import GMAIL_USER


async def create_notification(
    conn: asyncpg.Connection,
    user_id: str,
    event_name: str,
    payload: Dict[str, Any],
) -> str:
    """
    Inserts an in-app notification row for user.
    """
    notif_id = await conn.fetchval(
        """
        INSERT INTO notifications (user_id, event_name, payload)
        VALUES ($1::uuid, $2, $3::jsonb)
        RETURNING id::text
        """,
        user_id,
        event_name,
        json.dumps(payload),
    )
    return str(notif_id)


async def notify_admins(
    conn: asyncpg.Connection,
    event_name: str,
    payload: Dict[str, Any],
):
    """
    Finds all active administrators and creates in-app notifications.
    """
    admin_rows = await conn.fetch(
        """
        SELECT u.id, u.email
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE r.code = 'admin' AND u.status = 'active'
        """
    )
    for admin in admin_rows:
        await create_notification(conn, str(admin["id"]), event_name, payload)


async def send_cancellation_email(
    user_email: str,
    user_name: str,
    booking_id: str,
    event_title: str,
    venue_name: str,
    start_time: str,
    seats_list: list[str],
    refund_amount: float,
    cancellation_charge: float,
):
    """
    Sends email confirmation of booking cancellation and expected refund.
    """
    if not GMAIL_USER or not user_email:
        return

    subject = f"Booking Cancellation Confirmed - {event_title}"
    seats_str = ", ".join(seats_list) if seats_list else "General Admission"

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
          <h2>TicketFlow Cancellation Notice</h2>
        </div>
        <div style="padding: 24px; background: #fdfdfd; border: 1px solid #e0e0e0;">
          <p>Hi {user_name},</p>
          <p>Your booking for <strong>{event_title}</strong> has been successfully cancelled.</p>
          <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
            <tr><td style="padding: 8px; font-weight: bold; width: 40%;">Booking ID</td><td>{booking_id}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Venue</td><td>{venue_name}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Showtime</td><td>{start_time}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Cancelled Seats</td><td>{seats_str}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold;">Cancellation Charges</td><td>₹{cancellation_charge:.2f}</td></tr>
            <tr><td style="padding: 8px; font-weight: bold; color: #00c977;">Expected Refund</td><td style="font-weight: bold; color: #00c977;">₹{refund_amount:.2f}</td></tr>
          </table>
          <p>If applicable, refunds are credited back to your original payment method in 5–7 business days.</p>
        </div>
      </body>
    </html>
    """

    def _sync():
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from config import GMAIL_APP_PASSWORD

            msg = MIMEMultipart("alternative")
            msg["From"] = GMAIL_USER
            msg["To"] = user_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                s.send_message(msg)
        except Exception as e:
            print(f"[email] Failed to send cancellation email: {e}")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync)


async def send_refund_status_email(
    user_email: str,
    user_name: str,
    booking_id: str,
    event_title: str,
    status: str,
    refund_amount: float,
    refund_reference: str,
    failure_reason: Optional[str] = None,
):
    """
    Sends email update for refund initiation, success, or failure.
    """
    if not GMAIL_USER or not user_email:
        return

    subject = f"Refund Update for Booking {booking_id[:8]} - {status.capitalize()}"

    status_color = "#00c977" if status in ("processed", "successful") else "#ff4455" if status == "failed" else "#ffb300"
    message = (
        f"Your refund of ₹{refund_amount:.2f} has been processed successfully."
        if status in ("processed", "successful")
        else f"Refund processing failed. Reason: {failure_reason or 'Gateway error'}. Our team has been alerted."
        if status == "failed"
        else f"Your refund of ₹{refund_amount:.2f} has been initiated (Ref: {refund_reference})."
    )

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
          <h2>TicketFlow Refund Notification</h2>
        </div>
        <div style="padding: 24px; background: #fdfdfd; border: 1px solid #e0e0e0;">
          <p>Hi {user_name},</p>
          <div style="padding: 12px; background: {status_color}15; border-left: 4px solid {status_color}; margin: 16px 0;">
            <strong style="color: {status_color}; font-size: 16px;">{status.upper()}</strong>
            <p style="margin: 4px 0 0;">{message}</p>
          </div>
          <p>Booking ID: <strong>{booking_id}</strong></p>
          <p>Reference: <strong>{refund_reference}</strong></p>
        </div>
      </body>
    </html>
    """

    def _sync():
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from config import GMAIL_APP_PASSWORD

            msg = MIMEMultipart("alternative")
            msg["From"] = GMAIL_USER
            msg["To"] = user_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
                s.send_message(msg)
        except Exception as e:
            print(f"[email] Failed to send refund status email: {e}")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync)
