"""Forwarding accepted tickets, the Tickets overview, and email / WhatsApp delivery."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import ticket_transfer as svc
from services import transfer_notifier as notifier
from tests.test_ticket_transfers import (
    BOOKING_ID, FRIEND, FRIEND_ID, SEAT_A, SENDER, TRANSFER_ID, booking_row, make_conn, scan_row, transfer_row,
)

NEW_ID = "88888888-8888-8888-8888-888888888888"
THIRD = {"id": "99999999-9999-9999-9999-999999999999", "name": "Mira", "email": "mira@example.com", "status": "active"}
FRIEND_USER = {"id": FRIEND_ID, "name": "Ravi", "roles": ["customer"]}
HELD = [{"booking_seat_id": SEAT_A, "row_label": "B", "seat_number": 4}]


def accepted_parent(**over):
    base = {"status": "accepted", "to_user_id": FRIEND_ID, "is_used": False}
    return transfer_row(**{**base, **over})


@pytest.mark.asyncio
async def test_receiver_forwards_accepted_seat():
    conn = make_conn(
        fetchrow=[accepted_parent(), booking_row()], fetch=[[THIRD], HELD],
        fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID, NEW_ID],
    )
    result = await svc.forward_transfer(conn, FRIEND_USER, TRANSFER_ID, [SEAT_A], "mira@example.com")
    assert result["status"] == "pending" and result["seats"] == ["B4"]
    insert = next(c for c in conn.fetchval.await_args_list if "INSERT INTO ticket_transfers" in c.args[0])
    assert "parent_transfer_id" in insert.args[0] and insert.args[-1] == TRANSFER_ID
    assert any("INSERT INTO notifications" in c.args[0] for c in conn.execute.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("parent,message", [
    (lambda: accepted_parent(to_user_id=THIRD["id"]), "not found"),
    (lambda: accepted_parent(status="pending"), "accepted"),
    (lambda: accepted_parent(is_used=True), "already used"),
])
async def test_forward_refused_unless_receiver_holds_accepted_unused_tickets(parent, message):
    conn = make_conn(fetchrow=[parent(), booking_row()], fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID])
    with pytest.raises(svc.TransferError, match=message):
        await svc.forward_transfer(conn, FRIEND_USER, TRANSFER_ID, [SEAT_A], "mira@example.com")


@pytest.mark.asyncio
async def test_forward_refuses_seats_not_held_or_already_being_forwarded():
    conn = make_conn(fetchrow=[accepted_parent(), booking_row()], fetch=[[THIRD], []],
                     fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID])
    with pytest.raises(svc.TransferError, match="aren't yours"):
        await svc.forward_transfer(conn, FRIEND_USER, TRANSFER_ID, [SEAT_A], "mira@example.com")


@pytest.mark.asyncio
async def test_cannot_forward_to_yourself():
    conn = make_conn(fetchrow=[accepted_parent(), booking_row()], fetch=[[FRIEND]], fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID])
    with pytest.raises(svc.TransferError, match="yourself"):
        await svc.forward_transfer(conn, FRIEND_USER, TRANSFER_ID, [SEAT_A], "ravi@example.com")


PARENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.mark.asyncio
async def test_accepting_a_forward_releases_the_forwarders_seats():
    conn = make_conn(
        fetchrow=[transfer_row(parent_transfer_id=PARENT_ID), {"status": "accepted", "is_used": False}],
        fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID, 1, SENDER["id"]],
    )
    result = await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, True)
    assert result["status"] == "accepted"
    sql = [c.args[0] for c in conn.execute.await_args_list]
    assert any("SET released_at" in q for q in sql)
    events = [c.args[2] for c in conn.execute.await_args_list if "INSERT INTO notifications" in c.args[0]]
    assert events == ["transfer.accepted", "transfer.forwarded"]


@pytest.mark.asyncio
@pytest.mark.parametrize("parent", [{"status": "cancelled", "is_used": False}, {"status": "accepted", "is_used": True}, None])
async def test_forward_cannot_be_accepted_once_the_forwarder_lost_the_tickets(parent):
    conn = make_conn(fetchrow=[transfer_row(parent_transfer_id=PARENT_ID), parent], fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID])
    with pytest.raises(svc.TransferError, match="can no longer pass"):
        await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, True)


@pytest.mark.asyncio
async def test_seat_moved_by_someone_else_blocks_accept():
    conn = make_conn(
        fetchrow=[transfer_row(parent_transfer_id=PARENT_ID), {"status": "accepted", "is_used": False}],
        fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID, 2],
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")  # only 1 of 2 seats could be released
    with pytest.raises(svc.TransferError, match="no longer held"):
        await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, True)


@pytest.mark.asyncio
async def test_qr_of_fully_forwarded_tickets_is_rejected():
    conn = make_conn(fetchrow=[scan_row()], fetch=[[], []])
    with pytest.raises(svc.TransferError, match="forwarded"):
        await svc.scan_transfer_qr(conn, {"id": "m", "roles": ["admin"]}, "tok")
    conn.fetchval.assert_not_called()  # nothing was marked as used


@pytest.mark.asyncio
async def test_received_list_flags_forwardable_and_forwarded_seats():
    from tests.test_ticket_transfers import received_row
    items = [
        {"transfer_id": TRANSFER_ID, "booking_seat_id": SEAT_A, "released_at": None, "row_label": "B",
         "seat_number": 4, "forward_pending": False},
        {"transfer_id": TRANSFER_ID, "booking_seat_id": PARENT_ID, "released_at": "x", "row_label": "B",
         "seat_number": 5, "forward_pending": False},
    ]
    conn = make_conn(fetch=[[received_row()], [], [], items])
    [item] = await svc.list_received(conn, FRIEND_ID)
    assert item["seats"] == ["B4"] and item["forwarded_seats"] == ["B5"] and item["can_forward"] is True
    assert item["seat_items"][0]["booking_seat_id"] == SEAT_A and item["qr_data"]

    only_forwarded = [{**items[1]}]
    conn = make_conn(fetch=[[received_row()], [], [], only_forwarded])
    [item] = await svc.list_received(conn, FRIEND_ID)
    assert item["qr_data"] is None and item["can_forward"] is False


@pytest.mark.asyncio
async def test_overview_has_available_split_and_received():
    with patch.object(svc, "list_available", AsyncMock(return_value=["a"])), \
         patch.object(svc, "list_sent", AsyncMock(return_value=["s"])), \
         patch.object(svc, "list_received", AsyncMock(return_value=["r"])):
        assert await svc.tickets_overview(MagicMock(), "u") == {"available": ["a"], "split": ["s"], "received": ["r"]}


# ---------------------------------------------------------------------------
# Email + WhatsApp
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event", [
    "transfer.received", "transfer.payment_requested", "transfer.accepted", "transfer.declined",
    "transfer.cancelled", "transfer.expired", "transfer.forwarded", "transfer.payment_received",
    "transfer.payment_returned", "transfer.unknown",
])
def test_every_event_has_a_message(event):
    title, text = notifier.build_message(event, {"event_title": "Hamlet", "sender_name": "Asha",
                                                  "recipient_name": "Ravi", "amount_paise": 25050, "seats": ["B4"]})
    assert title and "Hamlet" in text


def test_payment_message_shows_rupees():
    assert "₹250.50" in notifier.build_message("transfer.payment_requested", {"amount_paise": 25050})[1]


@pytest.mark.parametrize("raw,expected", [
    ("98765 43210", "+919876543210"), ("+91 98765-43210", "+919876543210"),
    ("0987654321", None), ("12345", None), (None, None),
])
def test_whatsapp_number(raw, expected):
    assert notifier.whatsapp_number(raw) == expected


def delivery(channel, event="transfer.cancelled", attempts=1):
    return {"id": f"d-{channel}", "notification_id": "n1", "user_id": FRIEND_ID, "event_name": event,
            "channel": channel, "attempts": attempts}


def conn_for(deliveries, phone="98765 43210"):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=deliveries)
    conn.fetchrow = AsyncMock(return_value={"name": "Ravi", "email": "ravi@example.com", "phone": phone,
                                            "payload": '{"event_title": "Hamlet", "sender_name": "Asha"}'})
    conn.execute = AsyncMock()
    return conn


def statuses(conn):
    return {c.args[1]: c.args[2] for c in conn.execute.await_args_list}


@pytest.mark.asyncio
async def test_sends_email_and_whatsapp_and_records_both():
    conn = conn_for([delivery("email"), delivery("whatsapp")])
    wa, mail = AsyncMock(), AsyncMock()
    with patch.object(notifier, "whatsapp_configured", return_value=True), \
         patch.object(notifier, "_send_whatsapp", wa), patch.object(notifier, "_send_email", mail), \
         patch.object(notifier, "GMAIL_USER", "me@x.com"), patch.object(notifier, "GMAIL_APP_PASSWORD", "pw"):
        assert await notifier.deliver_pending(conn) == 2
    assert statuses(conn) == {"d-email": "sent", "d-whatsapp": "sent"}
    assert wa.await_args.args[0] == "+919876543210" and "Hamlet" in wa.await_args.args[1]


@pytest.mark.asyncio
async def test_skips_when_not_configured_or_no_phone_and_rich_emails():
    conn = conn_for([delivery("whatsapp"), delivery("email", event="transfer.received")])
    with patch.object(notifier, "whatsapp_configured", return_value=False):
        await notifier.deliver_pending(conn)
    assert statuses(conn) == {"d-whatsapp": "skipped", "d-email": "skipped"}

    conn = conn_for([delivery("whatsapp")], phone=None)
    with patch.object(notifier, "whatsapp_configured", return_value=True):
        await notifier.deliver_pending(conn)
    assert statuses(conn) == {"d-whatsapp": "skipped"}


@pytest.mark.asyncio
async def test_failed_message_is_retried_until_the_limit():
    for attempts, expected in [(1, "pending"), (notifier.MAX_ATTEMPTS, "failed")]:
        conn = conn_for([delivery("whatsapp", attempts=attempts)])
        with patch.object(notifier, "whatsapp_configured", return_value=True), \
             patch.object(notifier, "_send_whatsapp", AsyncMock(side_effect=RuntimeError("boom"))):
            assert await notifier.deliver_pending(conn) == 0
        assert statuses(conn) == {"d-whatsapp": expected}


@pytest.mark.asyncio
async def test_delivery_never_raises():
    conn = MagicMock()
    conn.fetch = AsyncMock(side_effect=RuntimeError("db down"))
    assert await notifier.deliver_pending(conn) == 0
