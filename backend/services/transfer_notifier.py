"""Automatic email + WhatsApp messages for split / transfer / payment events.

Every "transfer.*" row written to `notifications` gets two rows in
`transfer_message_deliveries` (email, whatsapp) from a database trigger (migration 0037).
`deliver_pending` sends them and records sent / failed / skipped, so nothing depends on
a request staying open and every delivery is visible in the database.

It runs right after each transfer request (background task) and every couple of
minutes from the app's cleanup loop, which also retries failures (max 5 attempts).
"""
import asyncio
import html
import logging
import re

import asyncpg
import httpx

from config import (
    FRONTEND_URL,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_FROM,
)
from services.transfer_email_service import _page, _send_sync

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BATCH = 20
# These already get a detailed email (seats, PDF) from the request that caused them.
RICH_EMAIL_EVENTS = {"transfer.received", "transfer.accepted", "transfer.declined"}


def _rupees(paise) -> str:
    try:
        return f"₹{int(paise) / 100:.2f}"
    except (TypeError, ValueError):
        return "the amount"


def build_message(event: str, payload: dict) -> tuple[str, str]:
    """(title, plain text) for an event. Text is also the WhatsApp body."""
    ev = payload.get("event_title") or "your show"
    sender = payload.get("sender_name") or "Someone"
    recipient = payload.get("recipient_name") or "Your friend"
    seats = ", ".join(payload.get("seats") or [])
    seat_part = f" ({seats})" if seats else ""
    if event == "transfer.received":
        verb = "forwarded you tickets" if payload.get("forwarded") else "sent you tickets"
        return "You received tickets", (
            f"{sender} {verb} for {ev}{seat_part}. Open TicketFlow > Tickets > Received within 24 hours to accept.")
    if event == "transfer.payment_requested":
        return "Payment requested", (
            f"{sender} asked for your share ({_rupees(payload.get('amount_paise'))}, test mode) for {ev}. "
            "Pay and accept from Tickets > Received.")
    if event == "transfer.accepted":
        return "Tickets accepted", f"{recipient} accepted the tickets you sent for {ev}."
    if event == "transfer.declined":
        return "Tickets declined", f"{recipient} declined the tickets you sent for {ev}. The seats are back with you."
    if event == "transfer.cancelled":
        return "Transfer cancelled", f"{sender} cancelled the tickets they sent you for {ev}."
    if event == "transfer.expired":
        return "Transfer expired", f"The ticket transfer for {ev} was not answered in time and has expired."
    if event == "transfer.forwarded":
        return "Your seats were forwarded", f"{sender} forwarded seats from your booking for {ev} to {recipient}."
    if event == "transfer.payment_received":
        return "Payment received", (
            f"{recipient} paid {_rupees(payload.get('amount_paise'))} (test mode) for their tickets to {ev}.")
    if event == "transfer.payment_returned":
        return "Payment returned", (
            f"The transfer for {ev} could not be completed, so your {_rupees(payload.get('amount_paise'))} "
            "test payment is being refunded.")
    return "Ticket update", f"There is an update on your ticket transfer for {ev}."


def whatsapp_number(phone: str | None) -> str | None:
    """+91XXXXXXXXXX for an Indian mobile number stored in any common format, else None."""
    digits = re.sub(r"\D", "", phone or "")[-10:]
    return f"+91{digits}" if re.fullmatch(r"[6-9]\d{9}", digits) else None


def whatsapp_configured() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM)


async def _send_whatsapp(to_number: str, body: str) -> None:
    from_ = TWILIO_WHATSAPP_FROM if TWILIO_WHATSAPP_FROM.startswith("whatsapp:") else f"whatsapp:{TWILIO_WHATSAPP_FROM}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={"From": from_, "To": f"whatsapp:{to_number}", "Body": body},
        )
    if resp.status_code >= 300:
        raise RuntimeError(f"WhatsApp provider returned {resp.status_code}")


async def _send_email(to_email: str, name: str, title: str, text: str) -> None:
    link = f"{FRONTEND_URL.rstrip('/')}/tickets"
    body = (f"<p>Hi {html.escape(name or 'there')},</p><p>{html.escape(text)}</p>"
            f'<p style="margin-top:20px;"><a href="{link}" style="color:#3b82f6;font-weight:600;">'
            "Open your tickets →</a></p>")
    # _send_sync returns quietly when SMTP is not configured; it raises on a real failure.
    await asyncio.get_running_loop().run_in_executor(None, _send_sync, to_email, title, _page(title, body), None)


async def _finish(conn: asyncpg.Connection, delivery_id, attempts: int, status: str, error: str | None = None) -> None:
    if status == "failed" and attempts < MAX_ATTEMPTS:
        status = "pending"  # try again on the next run
    await conn.execute(
        """UPDATE transfer_message_deliveries
           SET status = $2::varchar, last_error = $3, claimed_at = NULL,
               sent_at = CASE WHEN $2::varchar = 'sent' THEN now() ELSE sent_at END
           WHERE id = $1::uuid""",
        str(delivery_id), status, (error or "")[:300] or None,
    )


async def deliver_pending(conn: asyncpg.Connection, limit: int = BATCH) -> int:
    """Send queued messages. Never raises: a failed message is recorded and retried later."""
    try:
        rows = await conn.fetch(
            """UPDATE transfer_message_deliveries d
               SET status = 'sending', claimed_at = now(), attempts = d.attempts + 1
               WHERE d.id IN (
                   SELECT id FROM transfer_message_deliveries
                   WHERE attempts < $1
                     AND (status = 'pending' OR (status = 'sending' AND claimed_at < now() - interval '5 minutes'))
                   ORDER BY created_at LIMIT $2 FOR UPDATE SKIP LOCKED)
               RETURNING d.id, d.notification_id, d.user_id, d.event_name, d.channel, d.attempts""",
            MAX_ATTEMPTS, limit,
        )
    except Exception:
        logger.exception("Could not claim transfer messages")
        return 0
    sent = 0
    for d in rows:
        try:
            info = await conn.fetchrow(
                """SELECT u.name, u.email, u.phone, n.payload FROM notifications n
                   JOIN users u ON u.id = n.user_id WHERE n.id = $1::uuid""",
                str(d["notification_id"]),
            )
            if not info:
                await _finish(conn, d["id"], d["attempts"], "skipped", "notification or user missing")
                continue
            payload = info["payload"]
            if isinstance(payload, str):
                import json
                payload = json.loads(payload or "{}")
            title, text = build_message(d["event_name"], payload or {})
            if d["channel"] == "email":
                if d["event_name"] in RICH_EMAIL_EVENTS:
                    await _finish(conn, d["id"], d["attempts"], "skipped", "detailed email sent with the request")
                    continue
                if not info["email"]:
                    await _finish(conn, d["id"], d["attempts"], "skipped", "no email address")
                    continue
                if not (GMAIL_USER and GMAIL_APP_PASSWORD):
                    await _finish(conn, d["id"], d["attempts"], "skipped", "email is not configured")
                    continue
                await _send_email(info["email"], info["name"], title, text)
            else:
                number = whatsapp_number(info["phone"])
                if not whatsapp_configured():
                    await _finish(conn, d["id"], d["attempts"], "skipped", "WhatsApp is not configured")
                    continue
                if not number:
                    await _finish(conn, d["id"], d["attempts"], "skipped", "no valid mobile number on the profile")
                    continue
                await _send_whatsapp(number, f"TicketFlow: {text}")
            await _finish(conn, d["id"], d["attempts"], "sent")
            sent += 1
        except Exception as exc:  # one bad message must not stop the rest
            logger.warning("Transfer message %s failed: %s", d["id"], exc)
            try:
                await _finish(conn, d["id"], d["attempts"], "failed", str(exc))
            except Exception:
                logger.exception("Could not record transfer message failure")
    return sent


async def deliver_in_background() -> None:
    """Background-task entry point: opens its own connection from the pool."""
    from database import get_pool
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await deliver_pending(conn)
    except Exception:
        logger.exception("Transfer message delivery failed")
