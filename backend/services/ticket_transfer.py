"""Split and transfer tickets.

The owner of a confirmed booking sends some or all of its seats to another
TicketFlow user, found by email or phone number. The recipient accepts or
declines; the sender can cancel while the transfer is pending.

When a transfer is accepted its seats get their own QR code
(``TICKETFLOW-T:<token>``) and the booking's original QR stops admitting them.

Rules:
  * only the booking owner, only confirmed bookings, only before the show starts
  * not once the booking's QR has been scanned at the venue
  * not to yourself, and each seat can be in only one pending/accepted transfer
"""
from __future__ import annotations

import re
import secrets
import uuid
import json
from datetime import datetime, timezone
from typing import Optional

import asyncpg

TRANSFER_QR_PREFIX = "TICKETFLOW-T:"
ACTIVE = ("pending", "accepted")

PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")      # Indian mobile number, 10 digits
MAX_CONTACT_LENGTH = 255


class TransferError(Exception):
    """A rule was broken; the router turns this into an HTTP error."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def looks_like_email(value: str) -> bool:
    """name@domain.tld check without a regex (a regex here can be slow on crafted input)."""
    if value.count("@") != 1 or any(ch.isspace() for ch in value):
        return False
    local, domain = value.split("@")
    return (
        bool(local)
        and "." in domain
        and not domain.startswith(".")
        and not domain.endswith(".")
        and ".." not in domain
    )


def parse_recipient(raw: str) -> tuple[str, str]:
    """Return ("email", value) or ("phone", 10 digits) for what the sender typed."""
    value = (raw or "").strip()
    if not value:
        raise TransferError(400, "Enter the email or phone number of the person you're sending to")
    if len(value) > MAX_CONTACT_LENGTH:
        raise TransferError(400, "That email or phone number is too long")
    if "@" in value:
        if not looks_like_email(value):
            raise TransferError(400, "Enter a valid email address")
        return "email", value.lower()
    digits = re.sub(r"[\s\-()]", "", value)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not PHONE_PATTERN.match(digits):
        raise TransferError(400, "Enter a valid email or 10-digit Indian mobile number")
    return "phone", digits


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def seat_label(row: dict) -> str:
    return f"{row['row_label']}{row['seat_number']}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _started(start_time: Optional[datetime]) -> bool:
    if start_time is None:
        return False
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    return start_time <= _now()


async def _notify_transfer(conn: asyncpg.Connection, user_id: str, event_name: str, payload: dict) -> None:
    """Write the in-app notification in the same transaction as the transfer."""
    await conn.execute(
        """INSERT INTO notifications (user_id, event_name, payload)
           VALUES ($1::uuid, $2, $3::jsonb)""",
        user_id, event_name, json.dumps(payload),
    )


async def find_recipient(conn: asyncpg.Connection, kind: str, value: str) -> dict:
    if kind == "email":
        rows = await conn.fetch(
            "SELECT id, name, email, status FROM users WHERE lower(email) = $1", value
        )
    else:
        # Phones may be stored as "98765 43210", "+919876543210" ...: compare the last 10 digits.
        rows = await conn.fetch(
            """SELECT id, name, email, status FROM users
               WHERE right(regexp_replace(coalesce(phone, ''), '\\D', '', 'g'), 10) = $1""",
            value,
        )
    if not rows:
        what = "email" if kind == "email" else "phone number"
        raise TransferError(404, f"No TicketFlow account uses this {what}. Ask them to sign up first.")
    if len(rows) > 1:
        raise TransferError(409, "More than one account uses this phone number. Use their email instead.")
    user = dict(rows[0])
    if user["status"] != "active":
        raise TransferError(400, "This account can't receive tickets right now")
    return user


async def _seats_by_transfer(conn: asyncpg.Connection, transfer_ids: list) -> dict:
    if not transfer_ids:
        return {}
    rows = await conn.fetch(
        """SELECT tts.transfer_id, s.row_label, s.seat_number, s.seat_type
           FROM ticket_transfer_seats tts
           JOIN booking_seats bs ON bs.id = tts.booking_seat_id
           JOIN show_seats ss ON ss.id = bs.show_seat_id
           JOIN seats s ON s.id = ss.seat_id
           WHERE tts.transfer_id = ANY($1::uuid[])
           ORDER BY s.row_label, s.seat_number""",
        [str(t) for t in transfer_ids],
    )
    out: dict = {}
    for r in rows:
        out.setdefault(str(r["transfer_id"]), []).append(seat_label(r))
    zones = await conn.fetch(
        """SELECT tz.transfer_id, sz.name, tz.quantity FROM ticket_transfer_zones tz
           JOIN booking_zones bz ON bz.id = tz.booking_zone_id
           JOIN show_zones sz ON sz.id = bz.zone_id
           WHERE tz.transfer_id = ANY($1::uuid[]) ORDER BY sz.name""",
        [str(t) for t in transfer_ids],
    )
    for row in zones:
        out.setdefault(str(row["transfer_id"]), []).append(f"{row['name']} × {row['quantity']}")
    return out


_BOOKING_SQL = """
    SELECT b.id, b.user_id, b.status, s.start_time,
           e.title AS event_title, v.name AS venue_name, v.city, sc.name AS screen_name,
           u.name AS owner_name, u.email AS owner_email,
           t.status AS ticket_status, COALESCE(t.is_used, false) AS ticket_used
    FROM bookings b
    JOIN shows s    ON s.id = b.show_id
    JOIN events e   ON e.id = s.event_id
    JOIN screens sc ON sc.id = s.screen_id
    JOIN venues v   ON v.id = sc.venue_id
    JOIN users u    ON u.id = b.user_id
    LEFT JOIN tickets t ON t.booking_id = b.id
    WHERE b.id = $1::uuid
"""


def _transfer_block_reason(booking: dict) -> Optional[str]:
    """Why seats of this booking can't be sent right now (None = they can)."""
    if booking["status"] != "confirmed":
        return "Only confirmed bookings can be transferred"
    if booking["ticket_status"] == "cancelled":
        return "This ticket has been cancelled"
    if booking["ticket_used"] or booking["ticket_status"] == "used":
        return "This booking has already been scanned at the venue"
    if _started(booking["start_time"]):
        return "This show has already started"
    return None


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

async def _expire_transfers(
    conn: asyncpg.Connection, *, booking_id: str | None = None, user_id: str | None = None,
) -> None:
    await conn.execute(
        """WITH expired AS (
               UPDATE ticket_transfers tt SET status = 'expired', responded_at = clock_timestamp()
               FROM bookings b JOIN shows s ON s.id = b.show_id
               WHERE tt.booking_id = b.id AND tt.status = 'pending'
                 AND ($1::uuid IS NULL OR tt.booking_id = $1::uuid)
                 AND ($2::uuid IS NULL OR $2::uuid IN (tt.from_user_id, tt.to_user_id))
                 AND (tt.created_at + interval '24 hours' <= clock_timestamp()
                      OR s.start_time <= clock_timestamp())
               RETURNING tt.id, tt.booking_id, tt.from_user_id, tt.to_user_id, s.event_id
           )
           INSERT INTO public.notifications (user_id, event_name, payload)
           SELECT n.user_id, 'transfer.expired',
                  jsonb_build_object('transfer_id', x.id, 'booking_id', x.booking_id,
                                     'event_title', e.title, 'received', n.received)
           FROM expired x JOIN events e ON e.id = x.event_id
           CROSS JOIN LATERAL (VALUES (x.from_user_id, false), (x.to_user_id, true)) n(user_id, received)
           WHERE n.user_id IS NOT NULL""",
        booking_id, user_id,
    )


async def _expire_for_booking(conn: asyncpg.Connection, booking_id: str) -> None:
    await _expire_transfers(conn, booking_id=booking_id)


async def _expire_for_user(conn: asyncpg.Connection, user_id: str) -> None:
    await _expire_transfers(conn, user_id=user_id)


async def expire_pending_transfers(conn: asyncpg.Connection) -> None:
    """Expire transfers while a replica is running; request checks cover idle periods."""
    await _expire_transfers(conn)


async def booking_transfer_view(conn: asyncpg.Connection, user_id: str, booking_id: str) -> dict:
    """Seats of the user's booking with who holds each one, plus the booking's transfers."""
    if not is_uuid(booking_id):
        raise TransferError(404, "Booking not found")
    booking = await conn.fetchrow(_BOOKING_SQL, booking_id)
    if not booking or str(booking["user_id"]) != user_id:
        raise TransferError(404, "Booking not found")
    booking = dict(booking)
    await _expire_for_booking(conn, booking_id)

    seat_rows = await conn.fetch(
        """SELECT bs.id AS booking_seat_id, s.row_label, s.seat_number, s.seat_type,
                  bs.unit_price, tt.id AS transfer_id, tt.status AS transfer_status
           FROM booking_seats bs
           JOIN show_seats ss ON ss.id = bs.show_seat_id
           JOIN seats s ON s.id = ss.seat_id
           LEFT JOIN ticket_transfer_seats tts ON tts.booking_seat_id = bs.id
                AND EXISTS (SELECT 1 FROM ticket_transfers x
                            WHERE x.id = tts.transfer_id AND x.status IN ('pending', 'accepted'))
           LEFT JOIN ticket_transfers tt ON tt.id = tts.transfer_id
           WHERE bs.booking_id = $1::uuid
           ORDER BY s.row_label, s.seat_number""",
        booking_id,
    )
    transfer_rows = await conn.fetch(
        """SELECT tt.id, tt.status, tt.recipient_contact, tt.created_at, tt.responded_at, tt.is_used,
                  u.name AS recipient_name, tt.requested_share_paise, dp.amount_paise AS demo_amount,
                  CASE WHEN dp.refund_target = 'buyer' THEN dp.refund_status END AS demo_refund_status
           FROM ticket_transfers tt
           LEFT JOIN transfer_demo_payments dp ON dp.transfer_id = tt.id
           LEFT JOIN users u ON u.id = tt.to_user_id
           WHERE tt.booking_id = $1::uuid
           ORDER BY tt.created_at DESC""",
        booking_id,
    )
    seats_by_transfer = await _seats_by_transfer(conn, [r["id"] for r in transfer_rows])

    seats = [
        {
            "booking_seat_id": str(r["booking_seat_id"]),
            "label": seat_label(r),
            "seat_type": r["seat_type"],
            "price": float(r["unit_price"]),
            "state": {"pending": "pending", "accepted": "transferred"}.get(r["transfer_status"], "yours"),
            "transfer_id": str(r["transfer_id"]) if r["transfer_id"] else None,
        }
        for r in seat_rows
    ]
    zones = await available_zone_quantities(conn, booking_id)
    reason = _transfer_block_reason(booking)
    if reason is None and not any(s["state"] == "yours" for s in seats) and not any(z["available"] > 0 for z in zones):
        reason = "All seats on this booking have been sent to friends"

    return {
        "booking_id": booking_id,
        "event_title": booking["event_title"],
        "start_time": booking["start_time"].isoformat() if booking["start_time"] else None,
        "can_transfer": reason is None,
        "reason": reason,
        "seats": seats,
        "zones": zones,
        "transfers": [
            {
                "id": str(r["id"]),
                "status": r["status"],
                "recipient_name": r["recipient_name"] or r["recipient_contact"],
                "recipient_contact": r["recipient_contact"],
                "seats": seats_by_transfer.get(str(r["id"]), []),
                "used": r["is_used"],
                "demo_amount": r.get("demo_amount"),
                "requested_share_paise": r.get("requested_share_paise"),
                "demo_refund_status": r.get("demo_refund_status"),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "responded_at": r["responded_at"].isoformat() if r["responded_at"] else None,
            }
            for r in transfer_rows
        ],
    }


async def quote_demo_share(conn: asyncpg.Connection, transfer_id: str) -> dict:
    """Allocate the captured amount by item subtotal, rounded down to paise."""
    quote = await conn.fetchrow(
        """SELECT p.transaction_id, (p.amount * 100)::bigint AS captured_paise,
                  floor(p.amount * 100 *
                    (COALESCE((SELECT sum(bs.unit_price) FROM ticket_transfer_seats ts
                               JOIN booking_seats bs ON bs.id = ts.booking_seat_id
                               WHERE ts.transfer_id = tt.id), 0) +
                     COALESCE((SELECT sum(bz.unit_price * tz.quantity) FROM ticket_transfer_zones tz
                               JOIN booking_zones bz ON bz.id = tz.booking_zone_id
                               WHERE tz.transfer_id = tt.id), 0)) / NULLIF(b.subtotal_amount, 0)) AS amount
           FROM ticket_transfers tt JOIN bookings b ON b.id = tt.booking_id
           JOIN payments p ON p.booking_id = b.id
           WHERE tt.id = $1::uuid AND p.status = 'successful'
             AND p.payment_method = 'razorpay' AND p.currency = 'INR'
           ORDER BY p.paid_at DESC NULLS LAST LIMIT 1""", transfer_id,
    )
    if (not quote or not re.fullmatch(r"pay_[A-Za-z0-9]+", quote["transaction_id"] or "")
            or quote["amount"] is None
            or not 100 <= quote["amount"] <= min(quote["captured_paise"], 2_147_483_647)):
        raise TransferError(409, "This booking has no eligible test payment to reimburse")
    return dict(quote)


async def create_transfer(
    conn: asyncpg.Connection, sender: dict, booking_id: str, booking_seat_ids: list, recipient: str, zones: Optional[list] = None,
    *, request_demo_payment: bool = False,
) -> dict:
    """Create a pending transfer. Returns details for the API response and the email."""
    sender_id = str(sender["id"])
    if not is_uuid(booking_id):
        raise TransferError(404, "Booking not found")
    seat_ids = list(dict.fromkeys(str(s) for s in booking_seat_ids or []))
    zones = zones or []
    if not seat_ids and not zones:
        raise TransferError(400, "Choose at least one ticket to send")
    zone_ids = [str(z["booking_zone_id"]) for z in zones]
    if (len(zone_ids) != len(set(zone_ids)) or any(not is_uuid(zid) for zid in zone_ids)
            or any(type(z["quantity"]) is not int or z["quantity"] <= 0 for z in zones)):
        raise TransferError(400, "Invalid zone quantity")
    if not all(is_uuid(s) for s in seat_ids):
        raise TransferError(400, "Invalid seat in the request")
    kind, value = parse_recipient(recipient)

    async with conn.transaction():
        # Lock the booking so two transfers (or a cancellation) can't race for the same seats.
        locked = await conn.fetchrow(
            "SELECT id FROM bookings WHERE id = $1::uuid AND user_id = $2::uuid FOR UPDATE",
            booking_id, sender_id,
        )
        if not locked:
            raise TransferError(404, "Booking not found")
        booking = dict(await conn.fetchrow(_BOOKING_SQL, booking_id))
        reason = _transfer_block_reason(booking)
        if reason:
            raise TransferError(400, reason)

        try:
            to_user = await find_recipient(conn, kind, value)
        except TransferError as exc:
            if exc.status_code != 404 or kind != "email":
                raise
            to_user = None
        if to_user and str(to_user["id"]) == sender_id:
            raise TransferError(400, "You can't send tickets to yourself")

        await _expire_for_booking(conn, booking_id)
        free = await conn.fetch(
            """SELECT bs.id, s.row_label, s.seat_number
               FROM booking_seats bs
               JOIN show_seats ss ON ss.id = bs.show_seat_id
               JOIN seats s ON s.id = ss.seat_id
               WHERE bs.booking_id = $1::uuid AND bs.id = ANY($2::uuid[])
                 AND NOT EXISTS (
                     SELECT 1 FROM ticket_transfer_seats tts
                     JOIN ticket_transfers tt ON tt.id = tts.transfer_id
                     WHERE tts.booking_seat_id = bs.id AND tt.status IN ('pending', 'accepted'))
               ORDER BY s.row_label, s.seat_number""",
            booking_id, seat_ids,
        )
        if len(free) != len(seat_ids):
            raise TransferError(400, "Some of these seats aren't in this booking or were already sent to someone")

        available = {z["booking_zone_id"]: z for z in await available_zone_quantities(conn, booking_id)} if zones else {}
        if any(zid not in available or z["quantity"] > available[zid]["available"]
               for zid, z in zip(zone_ids, zones)):
            raise TransferError(400, "Some zone tickets are unavailable")

        transfer_id = await conn.fetchval(
            """INSERT INTO ticket_transfers (booking_id, from_user_id, to_user_id, recipient_contact)
               VALUES ($1::uuid, $2::uuid, $3::uuid, $4) RETURNING id""",
            booking_id, sender_id, str(to_user["id"]) if to_user else None, value,
        )
        await conn.execute(
            """INSERT INTO ticket_transfer_seats (transfer_id, booking_seat_id)
               SELECT $1::uuid, unnest($2::uuid[])""",
            str(transfer_id), seat_ids,
        )
        for zid, zone in zip(zone_ids, zones):
            await conn.execute(
                "INSERT INTO ticket_transfer_zones (transfer_id, booking_zone_id, quantity) VALUES ($1::uuid, $2::uuid, $3)",
                str(transfer_id), zid, zone["quantity"],
            )
        requested_share = None
        if request_demo_payment:
            quote = await quote_demo_share(conn, str(transfer_id))
            requested_share = int(quote["amount"])
            await conn.execute(
                "UPDATE ticket_transfers SET requested_share_paise = $2 WHERE id = $1::uuid",
                str(transfer_id), requested_share,
            )
        if to_user:
            await _notify_transfer(conn, str(to_user["id"]), "transfer.received", {
                "transfer_id": str(transfer_id),
                "event_title": booking["event_title"],
                "sender_name": sender.get("name") or "A TicketFlow user",
            })

    return {
        "id": str(transfer_id),
        "status": "pending",
        "recipient_name": to_user["name"] if to_user else value,
        "recipient_email": to_user["email"] if to_user else value,
        "invited": to_user is None,
        "recipient_contact": value,
        "requested_share_paise": requested_share,
        "seats": [seat_label(r) for r in free] + [f"{available[zid]['name']} × {z['quantity']}" for zid, z in zip(zone_ids, zones)],
        "event_title": booking["event_title"],
        "venue_name": booking["venue_name"],
        "city": booking["city"],
        "start_time": booking["start_time"],
        "sender_name": sender.get("name") or "A TicketFlow user",
    }


# ---------------------------------------------------------------------------
# Accept / decline / cancel
# ---------------------------------------------------------------------------

_TRANSFER_SQL = """
    SELECT tt.id, tt.booking_id, tt.from_user_id, tt.to_user_id, tt.status,
           b.status AS booking_status, s.start_time,
           t.status AS ticket_status, COALESCE(t.is_used, false) AS ticket_used,
           e.title AS event_title,
           fu.name AS sender_name, fu.email AS sender_email,
           tu.name AS recipient_name, tt.requested_share_paise,
           EXISTS (SELECT 1 FROM transfer_demo_payments dp WHERE dp.transfer_id = tt.id) AS demo_checkout
    FROM ticket_transfers tt
    JOIN bookings b ON b.id = tt.booking_id
    JOIN shows s    ON s.id = b.show_id
    JOIN events e   ON e.id = s.event_id
    JOIN users fu   ON fu.id = tt.from_user_id
    LEFT JOIN users tu ON tu.id = tt.to_user_id
    LEFT JOIN tickets t ON t.booking_id = b.id
    WHERE tt.id = $1::uuid
"""


async def _load_for_update(conn: asyncpg.Connection, transfer_id: str) -> Optional[dict]:
    if not is_uuid(transfer_id):
        return None
    booking_id = await conn.fetchval(
        "SELECT booking_id FROM ticket_transfers WHERE id = $1::uuid", transfer_id
    )
    if not booking_id:
        return None
    await conn.fetchval("SELECT id FROM bookings WHERE id = $1::uuid FOR UPDATE", str(booking_id))
    locked = await conn.fetchval(
        "SELECT id FROM ticket_transfers WHERE id = $1::uuid FOR UPDATE", transfer_id
    )
    if not locked:
        return None
    row = await conn.fetchrow(_TRANSFER_SQL, transfer_id)
    return dict(row) if row else None


async def respond_to_transfer(
    conn: asyncpg.Connection, user_id: str, transfer_id: str, accept: bool, *, paid_checkout: bool = False,
) -> dict:
    """Recipient accepts or declines a pending transfer."""
    if not paid_checkout:
        await _expire_for_user(conn, user_id)
    async with conn.transaction():
        tr = await _load_for_update(conn, transfer_id)
        if not tr or str(tr["to_user_id"]) != user_id:
            raise TransferError(404, "Transfer not found")
        if tr["status"] != "pending":
            raise TransferError(400, f"This transfer has already been {tr['status']}")

        if not accept:
            updated = await conn.execute(
                """UPDATE ticket_transfers tt SET status = 'declined', responded_at = clock_timestamp()
                   WHERE tt.id = $1::uuid AND tt.status = 'pending'
                     AND tt.created_at + interval '24 hours' > clock_timestamp()
                     AND EXISTS (SELECT 1 FROM bookings b JOIN shows s ON s.id = b.show_id
                                 WHERE b.id = tt.booking_id AND s.start_time > clock_timestamp())""",
                transfer_id,
            )
            if updated != "UPDATE 1":
                raise TransferError(400, "This transfer has expired")
            await _notify_transfer(conn, str(tr["from_user_id"]), "transfer.declined", {
                "transfer_id": transfer_id,
                "booking_id": str(tr["booking_id"]),
                "event_title": tr["event_title"],
                "recipient_name": tr["recipient_name"],
            })
            return {**tr, "status": "declined"}

        if (tr.get("requested_share_paise") or tr.get("demo_checkout")) and not paid_checkout:
            raise TransferError(409, "Finish or check your demo checkout before accepting these tickets")
        if tr["booking_status"] != "confirmed" or tr["ticket_status"] == "cancelled":
            raise TransferError(400, "This booking is no longer valid")
        if tr["ticket_used"] or tr["ticket_status"] == "used":
            raise TransferError(400, "The sender has already used this booking at the venue")
        if _started(tr["start_time"]):
            raise TransferError(400, "This show has already started")

        token = secrets.token_urlsafe(24)
        updated = await conn.execute(
            """UPDATE ticket_transfers tt
               SET status = 'accepted', qr_token = $2, responded_at = clock_timestamp()
               WHERE tt.id = $1::uuid AND tt.status = 'pending'
                 AND tt.created_at + interval '24 hours' > clock_timestamp()
                 AND EXISTS (SELECT 1 FROM bookings b JOIN shows s ON s.id = b.show_id
                             WHERE b.id = tt.booking_id AND s.start_time > clock_timestamp())""",
            transfer_id, token,
        )
        if updated != "UPDATE 1":
            raise TransferError(400, "This transfer has expired")
        await _notify_transfer(conn, str(tr["from_user_id"]), "transfer.accepted", {
            "transfer_id": transfer_id,
            "booking_id": str(tr["booking_id"]),
            "event_title": tr["event_title"],
            "recipient_name": tr["recipient_name"],
        })
        return {**tr, "status": "accepted"}


async def cancel_transfer(conn: asyncpg.Connection, user_id: str, transfer_id: str) -> dict:
    """Sender takes back a transfer the recipient hasn't answered yet."""
    await _expire_for_user(conn, user_id)
    async with conn.transaction():
        tr = await _load_for_update(conn, transfer_id)
        if not tr or str(tr["from_user_id"]) != user_id:
            raise TransferError(404, "Transfer not found")
        if tr["status"] != "pending":
            raise TransferError(400, f"Only pending transfers can be cancelled (this one is {tr['status']})")
        updated = await conn.execute(
            """UPDATE ticket_transfers tt SET status = 'cancelled', responded_at = clock_timestamp()
               WHERE tt.id = $1::uuid AND tt.status = 'pending'
                 AND tt.created_at + interval '24 hours' > clock_timestamp()
                 AND EXISTS (SELECT 1 FROM bookings b JOIN shows s ON s.id = b.show_id
                             WHERE b.id = tt.booking_id AND s.start_time > clock_timestamp())""",
            transfer_id,
        )
        if updated != "UPDATE 1":
            raise TransferError(400, "This transfer has expired")
        if tr["to_user_id"]:
            await _notify_transfer(conn, str(tr["to_user_id"]), "transfer.cancelled", {
                "transfer_id": transfer_id,
                "event_title": tr["event_title"],
                "sender_name": tr["sender_name"],
            })
        return {**tr, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Recipient
# ---------------------------------------------------------------------------

async def claim_verified_invitations(conn: asyncpg.Connection, user_id: str, email: str) -> None:
    """Attach invitations only after the caller's Firebase email has been verified."""
    await conn.execute(
        """WITH claimed AS (
               UPDATE ticket_transfers tt SET to_user_id = $1::uuid
               FROM bookings b JOIN shows s ON s.id = b.show_id
               WHERE tt.booking_id = b.id AND tt.to_user_id IS NULL AND tt.from_user_id <> $1::uuid
                 AND tt.status = 'pending' AND lower(tt.recipient_contact) = lower($2)
                 AND EXISTS (SELECT 1 FROM users u WHERE u.id = $1::uuid AND lower(u.email) = lower($2)
                             AND u.status = 'active')
                 AND tt.created_at + interval '24 hours' > clock_timestamp()
                 AND s.start_time > clock_timestamp() AND b.status = 'confirmed'
                 AND NOT EXISTS (SELECT 1 FROM tickets t WHERE t.booking_id = b.id
                                 AND (t.is_used OR t.status IN ('used', 'cancelled')))
               RETURNING tt.id, tt.from_user_id, s.event_id
           )
           INSERT INTO notifications (user_id, event_name, payload)
           SELECT $1::uuid, 'transfer.received',
                  jsonb_build_object('transfer_id', c.id, 'event_title', e.title, 'sender_name', u.name)
           FROM claimed c JOIN events e ON e.id = c.event_id JOIN users u ON u.id = c.from_user_id""",
        user_id, email,
    )


async def list_received(conn: asyncpg.Connection, user_id: str) -> list[dict]:
    await _expire_for_user(conn, user_id)
    rows = await conn.fetch(
        """SELECT tt.id, tt.status, tt.qr_token, tt.is_used, tt.created_at, tt.booking_id,
                  b.status AS booking_status, t.status AS ticket_status,
                  e.title AS event_title, e.poster_url, s.start_time,
                  v.name AS venue_name, v.city, sc.name AS screen_name,
                  fu.name AS sender_name, tt.requested_share_paise, dp.amount_paise AS demo_amount,
                  dp.refund_target AS demo_refund_target, dp.refund_status AS demo_refund_status
           FROM ticket_transfers tt
           LEFT JOIN transfer_demo_payments dp ON dp.transfer_id = tt.id
           JOIN bookings b ON b.id = tt.booking_id
           JOIN shows s    ON s.id = b.show_id
           JOIN events e   ON e.id = s.event_id
           JOIN screens sc ON sc.id = s.screen_id
           JOIN venues v   ON v.id = sc.venue_id
           JOIN users fu   ON fu.id = tt.from_user_id
           LEFT JOIN tickets t ON t.booking_id = b.id
           WHERE tt.to_user_id = $1::uuid
           ORDER BY s.start_time DESC, tt.created_at DESC""",
        user_id,
    )
    seats = await _seats_by_transfer(conn, [r["id"] for r in rows])
    out = []
    for r in rows:
        cancelled = r["booking_status"] == "cancelled" or r["ticket_status"] == "cancelled"
        show_qr = r["status"] == "accepted" and not cancelled
        out.append({
            "id": str(r["id"]),
            "status": "booking_cancelled" if cancelled and r["status"] == "accepted" else r["status"],
            "used": r["is_used"],
            "demo_amount": r.get("demo_amount"),
            "requested_share_paise": r.get("requested_share_paise"),
            "demo_refund_target": r.get("demo_refund_target"),
            "demo_refund_status": r.get("demo_refund_status"),
            "sender_name": r["sender_name"],
            "event_title": r["event_title"],
            "poster_url": r["poster_url"],
            "start_time": r["start_time"].isoformat() if r["start_time"] else None,
            "venue_name": r["venue_name"],
            "city": r["city"],
            "screen_name": r["screen_name"],
            "seats": seats.get(str(r["id"]), []),
            "qr_data": f"{TRANSFER_QR_PREFIX}{r['qr_token']}" if show_qr else None,
        })
    return out


# ---------------------------------------------------------------------------
# Venue entry
# ---------------------------------------------------------------------------

async def scan_transfer_qr(conn: asyncpg.Connection, scanner: dict, token: str) -> dict:
    """Admit the seats of an accepted transfer (manager of the event's organisation or admin)."""
    token = (token or "").strip()
    if not token:
        raise TransferError(400, "Invalid ticket QR code")
    row = await conn.fetchrow(
        """SELECT tt.id, tt.booking_id, tt.is_used, b.status AS booking_status, t.status AS ticket_status,
                  e.title AS event_title, s.start_time, v.name AS venue_name, sc.name AS screen_name,
                  u.name AS user_name, u.email AS user_email,
                  (
                      EXISTS (SELECT 1 FROM organizer_profiles op
                              WHERE op.id = e.organizer_id AND op.user_id = $2::uuid)
                      OR
                      EXISTS (SELECT 1 FROM venue_verification_cases vc
                              WHERE vc.venue_id = v.id AND vc.applicant_id = $2::uuid)
                  ) AS is_owner
           FROM ticket_transfers tt
           JOIN bookings b ON b.id = tt.booking_id
           JOIN shows s    ON s.id = b.show_id
           JOIN events e   ON e.id = s.event_id
           JOIN screens sc ON sc.id = s.screen_id
           JOIN venues v   ON v.id = sc.venue_id
           JOIN users u    ON u.id = tt.to_user_id
           LEFT JOIN tickets t ON t.booking_id = b.id
           WHERE tt.qr_token = $1 AND tt.status = 'accepted'""",
        token, str(scanner["id"]),
    )
    is_admin = "admin" in (scanner.get("roles") or [])
    if not row or (not is_admin and not row["is_owner"]):
        raise TransferError(404, "Ticket not found")
    if row["booking_status"] == "cancelled" or row["ticket_status"] == "cancelled":
        raise TransferError(400, "Ticket has been cancelled and cannot be used for entry")
    if row["is_used"]:
        raise TransferError(409, "Ticket has already been scanned and used. Duplicate entry is not permitted.")

    updated = await conn.fetchval(
        """UPDATE ticket_transfers SET is_used = true, used_at = now()
           WHERE id = $1::uuid AND is_used = false RETURNING id""",
        str(row["id"]),
    )
    if not updated:
        raise TransferError(409, "Ticket was already scanned and consumed by another scanner")
    seats = (await _seats_by_transfer(conn, [row["id"]])).get(str(row["id"]), [])
    return {
        "success": True,
        "valid": True,
        "message": "Ticket validated successfully. Admitted for entry.",
        "transfer_id": str(row["id"]),
        "booking_id": str(row["booking_id"]),
        "used": True,
        "seats": seats,
        "attendee": {"name": row["user_name"], "email": row["user_email"]},
        "event": {
            "title": row["event_title"],
            "venue": row["venue_name"],
            "screen": row["screen_name"],
            "start_time": row["start_time"].isoformat() if row["start_time"] else None,
        },
    }


async def seats_left_on_booking(conn: asyncpg.Connection, booking_id: str) -> tuple[int, list[str]]:
    """(numbered seats on the booking, labels still held by the booker) — for the booking's own QR."""
    rows = await conn.fetch(
        """SELECT s.row_label, s.seat_number,
                  EXISTS (SELECT 1 FROM ticket_transfer_seats tts
                          JOIN ticket_transfers tt ON tt.id = tts.transfer_id
                          WHERE tts.booking_seat_id = bs.id AND tt.status = 'accepted') AS transferred
           FROM booking_seats bs
           JOIN show_seats ss ON ss.id = bs.show_seat_id
           JOIN seats s ON s.id = ss.seat_id
           WHERE bs.booking_id = $1::uuid
           ORDER BY s.row_label, s.seat_number""",
        booking_id,
    )
    return len(rows), [seat_label(r) for r in rows if not r["transferred"]]


async def close_pending_for_booking(conn: asyncpg.Connection, booking_id: str) -> None:
    """Cancel transfers nobody answered (used when the booking is scanned or cancelled)."""
    await _expire_for_booking(conn, booking_id)
    await conn.execute(
        """WITH closed AS (
               UPDATE ticket_transfers SET status = 'cancelled', responded_at = clock_timestamp()
               WHERE booking_id = $1::uuid AND status = 'pending'
               RETURNING id, booking_id, to_user_id
           )
           INSERT INTO notifications (user_id, event_name, payload)
           SELECT x.to_user_id, 'transfer.cancelled',
                  jsonb_build_object('transfer_id', x.id, 'event_title', e.title,
                                     'closed_with_booking', true)
           FROM closed x JOIN bookings b ON b.id = x.booking_id
           JOIN shows s ON s.id = b.show_id JOIN events e ON e.id = s.event_id
           WHERE x.to_user_id IS NOT NULL""",
        booking_id,
    )


async def has_accepted_transfers(conn: asyncpg.Connection, booking_id: str) -> bool:
    return bool(await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM ticket_transfers WHERE booking_id = $1::uuid AND status = 'accepted')",
        booking_id,
    ))


async def received_ticket_data(conn: asyncpg.Connection, user_id: str, transfer_id: str) -> dict:
    """Everything needed for the recipient's PDF / email ticket (accepted transfers only)."""
    if not is_uuid(transfer_id):
        raise TransferError(404, "Ticket not found")
    row = await conn.fetchrow(
        """SELECT tt.id, tt.to_user_id, tt.status, tt.qr_token, tt.booking_id,
                  b.status AS booking_status, t.status AS ticket_status,
                  e.title AS event_title, s.start_time, v.name AS venue_name, v.city,
                  sc.name AS screen_name, tu.name AS user_name, tu.email AS user_email,
                  fu.name AS sender_name
           FROM ticket_transfers tt
           JOIN bookings b ON b.id = tt.booking_id
           JOIN shows s    ON s.id = b.show_id
           JOIN events e   ON e.id = s.event_id
           JOIN screens sc ON sc.id = s.screen_id
           JOIN venues v   ON v.id = sc.venue_id
           JOIN users tu   ON tu.id = tt.to_user_id
           JOIN users fu   ON fu.id = tt.from_user_id
           LEFT JOIN tickets t ON t.booking_id = b.id
           WHERE tt.id = $1::uuid""",
        transfer_id,
    )
    if not row or str(row["to_user_id"]) != user_id or row["status"] != "accepted":
        raise TransferError(404, "Ticket not found")
    if row["booking_status"] == "cancelled" or row["ticket_status"] == "cancelled":
        raise TransferError(400, "This booking was cancelled, so the ticket is no longer valid")
    seats = await conn.fetch(
        """SELECT s.row_label, s.seat_number, s.seat_type, bs.unit_price AS price
           FROM ticket_transfer_seats tts
           JOIN booking_seats bs ON bs.id = tts.booking_seat_id
           JOIN show_seats ss ON ss.id = bs.show_seat_id
           JOIN seats s ON s.id = ss.seat_id
           WHERE tts.transfer_id = $1::uuid
           ORDER BY s.row_label, s.seat_number""",
        transfer_id,
    )
    seat_list = [dict(r) for r in seats]
    zone_rows = await conn.fetch(
        """SELECT sz.name, tz.quantity, bz.unit_price FROM ticket_transfer_zones tz
           JOIN booking_zones bz ON bz.id = tz.booking_zone_id
           JOIN show_zones sz ON sz.id = bz.zone_id WHERE tz.transfer_id = $1::uuid""", transfer_id,
    )
    seat_list.extend({"row_label": z["name"], "seat_number": f" × {z['quantity']}",
                      "seat_type": "standing", "price": z["unit_price"] * z["quantity"]} for z in zone_rows)
    return {
        "transfer_id": str(row["id"]),
        # the PDF prints this as the ticket reference; the transfer id is the recipient's own reference
        "booking_id": str(row["id"]),
        "event_title": row["event_title"],
        "venue_name": row["venue_name"],
        "venue_city": row["city"],
        "screen_name": row["screen_name"],
        "start_time": row["start_time"],
        "seats": seat_list,
        "total_amount": float(sum(float(s["price"]) for s in seat_list)),
        "user_name": f"{row['user_name']} (from {row['sender_name']})",
        "recipient_name": row["user_name"],
        "user_email": row["user_email"],
        "sender_name": row["sender_name"],
        "qr_data": f"{TRANSFER_QR_PREFIX}{row['qr_token']}",
    }


async def list_admin_transfers(conn: asyncpg.Connection, page: int, page_size: int) -> dict:
    total = await conn.fetchval("SELECT COUNT(*) FROM ticket_transfers")
    rows = await conn.fetch(
        """SELECT tt.id, tt.created_at,
                  CASE WHEN tt.status = 'pending' AND
                    (tt.created_at + interval '24 hours' <= statement_timestamp()
                     OR s.start_time <= statement_timestamp()) THEN 'expired' ELSE tt.status END AS status,
                  e.title AS event_title,
                  sender.name AS sender_name, COALESCE(recipient.name, tt.recipient_contact) AS recipient_name,
                  ((SELECT COUNT(*) FROM ticket_transfer_seats ts WHERE ts.transfer_id = tt.id) +
                   COALESCE((SELECT SUM(tz.quantity) FROM ticket_transfer_zones tz WHERE tz.transfer_id = tt.id), 0)) AS seats
           FROM ticket_transfers tt JOIN bookings b ON b.id = tt.booking_id
           JOIN shows s ON s.id = b.show_id JOIN events e ON e.id = s.event_id
           JOIN users sender ON sender.id = tt.from_user_id
           LEFT JOIN users recipient ON recipient.id = tt.to_user_id
           ORDER BY tt.created_at DESC, tt.id DESC LIMIT $1 OFFSET $2""",
        page_size, (page - 1) * page_size,
    )
    return {"total": total, "page": page, "transfers": [dict(row) for row in rows]}


async def available_zone_quantities(conn: asyncpg.Connection, booking_id: str) -> list[dict]:
    """Return each zone's unallocated quantity; caller serializes changes with the booking lock."""
    rows = await conn.fetch(
        """SELECT bz.id, sz.name, bz.quantity,
                  COALESCE(SUM(tz.quantity) FILTER (WHERE tt.status IN ('pending', 'accepted')), 0) AS allocated
           FROM booking_zones bz JOIN show_zones sz ON sz.id = bz.zone_id
           LEFT JOIN ticket_transfer_zones tz ON tz.booking_zone_id = bz.id
           LEFT JOIN ticket_transfers tt ON tt.id = tz.transfer_id
           WHERE bz.booking_id = $1::uuid
           GROUP BY bz.id, sz.name, bz.quantity ORDER BY sz.name, bz.id""",
        booking_id,
    )
    return [{"booking_zone_id": str(row["id"]), "name": row["name"],
             "quantity": row["quantity"], "available": row["quantity"] - int(row["allocated"])}
            for row in rows]


async def zones_left_on_booking(conn: asyncpg.Connection, booking_id: str) -> list[dict]:
    """Standing tickets the original QR can admit after accepted transfers."""
    rows = await conn.fetch(
        """SELECT bz.id, sz.name, bz.quantity, bz.unit_price,
                  COALESCE(SUM(tz.quantity) FILTER (WHERE tt.status = 'accepted'), 0) AS transferred
           FROM booking_zones bz JOIN show_zones sz ON sz.id = bz.zone_id
           LEFT JOIN ticket_transfer_zones tz ON tz.booking_zone_id = bz.id
           LEFT JOIN ticket_transfers tt ON tt.id = tz.transfer_id
           WHERE bz.booking_id = $1::uuid
           GROUP BY bz.id, sz.name, bz.quantity ORDER BY sz.name, bz.id""", booking_id,
    )
    return [{"booking_zone_id": str(r["id"]), "name": r["name"],
             "quantity": r["quantity"] - int(r["transferred"]), "unit_price": r["unit_price"]} for r in rows]
