from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from routers import ticket_transfers as transfer_router
from routers.tickets import TicketScanRequest, _scan_and_consume_ticket, scan_ticket
from services import ticket_transfer as svc
from services.transfer_email_service import build_received_email, build_response_email

SENDER = {"id": "11111111-1111-1111-1111-111111111111", "name": "Asha", "roles": ["customer"]}
FRIEND_ID = "22222222-2222-2222-2222-222222222222"
BOOKING_ID = "33333333-3333-3333-3333-333333333333"
TRANSFER_ID = "44444444-4444-4444-4444-444444444444"
SEAT_A = "55555555-5555-5555-5555-555555555555"
SEAT_B = "66666666-6666-6666-6666-666666666666"
MANAGER = {"id": "77777777-7777-7777-7777-777777777777", "roles": ["manager"]}

FUTURE = datetime.now(timezone.utc) + timedelta(days=2)
PAST = datetime.now(timezone.utc) - timedelta(hours=1)


def make_conn(fetchrow=(), fetch=(), fetchval=()):
    """Fake asyncpg connection: each call returns the next scripted result."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=list(fetchrow))
    conn.fetch = AsyncMock(side_effect=list(fetch))
    conn.fetchval = AsyncMock(side_effect=list(fetchval))
    conn.execute = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    return conn


def booking_row(**over):
    row = {
        "id": BOOKING_ID, "user_id": SENDER["id"], "status": "confirmed", "start_time": FUTURE,
        "event_title": "Hamlet", "venue_name": "NMS Stage", "city": "Ahmedabad", "screen_name": "Main",
        "owner_name": "Asha", "owner_email": "asha@example.com",
        "ticket_status": "valid", "ticket_used": False,
    }
    row.update(over)
    return row


FRIEND = {"id": FRIEND_ID, "name": "Ravi", "email": "ravi@example.com", "status": "active"}
FREE_SEATS = [{"id": SEAT_A, "row_label": "B", "seat_number": 4}, {"id": SEAT_B, "row_label": "B", "seat_number": 5}]


def transfer_row(**over):
    row = {
        "id": TRANSFER_ID, "booking_id": BOOKING_ID, "from_user_id": SENDER["id"], "to_user_id": FRIEND_ID,
        "status": "pending", "booking_status": "confirmed", "start_time": FUTURE,
        "ticket_status": "valid", "ticket_used": False, "event_title": "Hamlet",
        "sender_name": "Asha", "sender_email": "asha@example.com", "recipient_name": "Ravi",
    }
    row.update(over)
    return row


# ---------------------------------------------------------------------------
# Recipient parsing and lookup
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Ravi@Example.com ", ("email", "ravi@example.com")),
    ("98765 43210", ("phone", "9876543210")),
    ("+91-98765-43210", ("phone", "9876543210")),
    ("09876543210", ("phone", "9876543210")),
])
def test_parse_recipient(raw, expected):
    assert svc.parse_recipient(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "   ", "ravi@", "@example.com", "ravi@example", "ravi@.com", "ravi@example.", "ravi@exa..com",
    "ra vi@example.com", "a@b@example.com", "12345", "5876543210", "x" * 300,
    "!@!." + "!." * 120,  # crafted input from the CodeQL alert: must be rejected quickly
])
def test_parse_recipient_rejects_bad_input(raw):
    with pytest.raises(svc.TransferError) as exc:
        svc.parse_recipient(raw)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_unknown_recipient_is_404():
    with pytest.raises(svc.TransferError) as exc:
        await svc.find_recipient(make_conn(fetch=[[]]), "email", "nobody@example.com")
    assert exc.value.status_code == 404
    assert "sign up" in exc.value.detail


@pytest.mark.asyncio
async def test_shared_phone_number_asks_for_email():
    with pytest.raises(svc.TransferError) as exc:
        await svc.find_recipient(make_conn(fetch=[[FRIEND, {**FRIEND, "id": "x"}]]), "phone", "9876543210")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_blocked_recipient_cannot_receive():
    with pytest.raises(svc.TransferError):
        await svc.find_recipient(make_conn(fetch=[[{**FRIEND, "status": "blocked"}]]), "email", "ravi@example.com")


# ---------------------------------------------------------------------------
# Creating a transfer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_transfer_success():
    conn = make_conn(
        fetchrow=[{"id": BOOKING_ID}, booking_row()],
        fetch=[[FRIEND], FREE_SEATS],
        fetchval=[TRANSFER_ID],
    )
    result = await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A, SEAT_B, SEAT_A], "ravi@example.com")

    assert result["status"] == "pending"
    assert result["seats"] == ["B4", "B5"]
    assert result["recipient_email"] == "ravi@example.com"
    # the booking row is locked and must belong to the sender
    assert "FOR UPDATE" in conn.fetchrow.await_args_list[0].args[0]
    assert conn.fetchrow.await_args_list[0].args[1:] == (BOOKING_ID, SENDER["id"])
    insert = conn.fetchval.await_args
    assert insert.args[1:] == (BOOKING_ID, SENDER["id"], FRIEND_ID, "ravi@example.com")
    # duplicates removed before saving the seats
    assert conn.execute.await_args.args[1:] == (TRANSFER_ID, [SEAT_A, SEAT_B])


@pytest.mark.asyncio
async def test_cannot_transfer_someone_elses_booking():
    conn = make_conn(fetchrow=[None])
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A], "ravi@example.com")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("over,message", [
    ({"status": "pending"}, "confirmed"),
    ({"ticket_status": "cancelled"}, "cancelled"),
    ({"ticket_used": True}, "scanned"),
    ({"start_time": PAST}, "started"),
])
async def test_transfer_blocked_by_booking_state(over, message):
    conn = make_conn(fetchrow=[{"id": BOOKING_ID}, booking_row(**over)])
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A], "ravi@example.com")
    assert exc.value.status_code == 400
    assert message in exc.value.detail
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_cannot_send_to_yourself():
    me = {**FRIEND, "id": SENDER["id"]}
    conn = make_conn(fetchrow=[{"id": BOOKING_ID}, booking_row()], fetch=[[me]])
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A], "asha@example.com")
    assert "yourself" in exc.value.detail


@pytest.mark.asyncio
async def test_seat_already_sent_is_rejected():
    conn = make_conn(fetchrow=[{"id": BOOKING_ID}, booking_row()], fetch=[[FRIEND], FREE_SEATS[:1]])
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A, SEAT_B], "ravi@example.com")
    assert exc.value.status_code == 400
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("booking_id,seats,status", [
    ("not-a-uuid", [SEAT_A], 404),
    (BOOKING_ID, [], 400),
    (BOOKING_ID, ["bad"], 400),
])
async def test_create_transfer_validates_ids(booking_id, seats, status):
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(make_conn(), SENDER, booking_id, seats, "ravi@example.com")
    assert exc.value.status_code == status


# ---------------------------------------------------------------------------
# Accept / decline / cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_gives_the_seats_a_new_qr_token():
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row()])
    result = await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=True)
    assert result["status"] == "accepted"
    sql, tid, token = conn.execute.await_args.args
    assert "status = 'accepted'" in sql and tid == TRANSFER_ID
    assert len(token) >= 24


@pytest.mark.asyncio
async def test_decline():
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row()])
    result = await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=False)
    assert result["status"] == "declined"
    assert "declined" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_only_the_recipient_can_answer():
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row()])
    with pytest.raises(svc.TransferError) as exc:
        await svc.respond_to_transfer(conn, SENDER["id"], TRANSFER_ID, accept=True)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("over", [
    {"status": "cancelled"},
    {"ticket_used": True},
    {"booking_status": "cancelled"},
    {"start_time": PAST},
])
async def test_accept_refused_when_no_longer_valid(over):
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row(**over)])
    with pytest.raises(svc.TransferError) as exc:
        await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=True)
    assert exc.value.status_code == 400
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_sender_cancels_pending_transfer():
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row()])
    assert (await svc.cancel_transfer(conn, SENDER["id"], TRANSFER_ID))["status"] == "cancelled"


@pytest.mark.asyncio
async def test_accepted_transfer_cannot_be_cancelled():
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row(status="accepted")])
    with pytest.raises(svc.TransferError) as exc:
        await svc.cancel_transfer(conn, SENDER["id"], TRANSFER_ID)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_recipient_cannot_cancel_and_bad_id_is_404():
    conn = make_conn(fetchval=[TRANSFER_ID], fetchrow=[transfer_row()])
    with pytest.raises(svc.TransferError):
        await svc.cancel_transfer(conn, FRIEND_ID, TRANSFER_ID)
    with pytest.raises(svc.TransferError) as exc:
        await svc.cancel_transfer(make_conn(), SENDER["id"], "nope")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# Received list
# ---------------------------------------------------------------------------

def received_row(**over):
    row = {
        "id": TRANSFER_ID, "status": "accepted", "qr_token": "tok123", "is_used": False,
        "created_at": FUTURE, "booking_id": BOOKING_ID, "booking_status": "confirmed",
        "ticket_status": "valid", "event_title": "Hamlet", "poster_url": None, "start_time": FUTURE,
        "venue_name": "NMS Stage", "city": "Ahmedabad", "screen_name": "Main", "sender_name": "Asha",
    }
    row.update(over)
    return row


@pytest.mark.asyncio
async def test_received_shows_qr_only_for_valid_accepted_transfers():
    seats = [{"transfer_id": TRANSFER_ID, "row_label": "B", "seat_number": 4, "seat_type": "standard"}]
    conn = make_conn(fetch=[[received_row()], seats])
    [item] = await svc.list_received(conn, FRIEND_ID)
    assert item["qr_data"] == "TICKETFLOW-T:tok123"
    assert item["seats"] == ["B4"]

    conn = make_conn(fetch=[[received_row(status="pending", qr_token=None)], []])
    assert (await svc.list_received(conn, FRIEND_ID))[0]["qr_data"] is None

    conn = make_conn(fetch=[[received_row(booking_status="cancelled")], []])
    [item] = await svc.list_received(conn, FRIEND_ID)
    assert item["qr_data"] is None and item["status"] == "booking_cancelled"


# ---------------------------------------------------------------------------
# Venue entry
# ---------------------------------------------------------------------------

def scan_row(**over):
    row = {
        "id": TRANSFER_ID, "booking_id": BOOKING_ID, "is_used": False, "booking_status": "confirmed",
        "ticket_status": "valid", "event_title": "Hamlet", "start_time": FUTURE, "venue_name": "NMS Stage",
        "screen_name": "Main", "user_name": "Ravi", "user_email": "ravi@example.com", "is_owner": True,
    }
    row.update(over)
    return row


@pytest.mark.asyncio
async def test_scan_transfer_qr_admits_once():
    seats = [{"transfer_id": TRANSFER_ID, "row_label": "B", "seat_number": 4, "seat_type": "standard"}]
    conn = make_conn(fetchrow=[scan_row()], fetchval=[TRANSFER_ID], fetch=[seats])
    result = await svc.scan_transfer_qr(conn, MANAGER, "tok123")
    assert result["valid"] is True and result["seats"] == ["B4"]
    assert conn.fetchrow.await_args.args[1:] == ("tok123", MANAGER["id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("over,status", [
    ({"is_owner": False}, 404),
    ({"is_used": True}, 409),
    ({"booking_status": "cancelled"}, 400),
])
async def test_scan_transfer_qr_rejections(over, status):
    with pytest.raises(svc.TransferError) as exc:
        await svc.scan_transfer_qr(make_conn(fetchrow=[scan_row(**over)]), MANAGER, "tok123")
    assert exc.value.status_code == status


@pytest.mark.asyncio
async def test_scan_endpoint_routes_transfer_qr_codes():
    with patch("routers.tickets.transfers.scan_transfer_qr", new=AsyncMock(return_value={"valid": True})) as scan:
        result = await scan_ticket(TicketScanRequest(qr_data="TICKETFLOW-T:AbC_123"), MANAGER, make_conn())
    assert result == {"valid": True}
    assert scan.await_args.args[2] == "AbC_123"   # token keeps its case


@pytest.mark.asyncio
async def test_booking_qr_refused_when_every_seat_was_transferred():
    ticket = {"id": "t1", "booking_id": BOOKING_ID, "status": "valid", "is_used": False, "is_owner": True}
    seats = [{"row_label": "B", "seat_number": 4, "transferred": True}]
    conn = make_conn(fetchrow=[ticket], fetch=[seats])
    with pytest.raises(HTTPException) as exc:
        await _scan_and_consume_ticket(BOOKING_ID, MANAGER, conn)
    assert exc.value.status_code == 409
    assert "transferred" in exc.value.detail


# ---------------------------------------------------------------------------
# Router and emails
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_router_turns_rule_errors_into_http_errors():
    with patch.object(transfer_router.svc, "create_transfer",
                      new=AsyncMock(side_effect=svc.TransferError(400, "nope"))):
        body = transfer_router.TransferCreate(booking_id=BOOKING_ID, seat_ids=[SEAT_A], recipient="x@y.com")
        with pytest.raises(HTTPException) as exc:
            await transfer_router.create_transfer(body, BackgroundTasks(), SENDER, make_conn())
    assert exc.value.status_code == 400 and exc.value.detail == "nope"


@pytest.mark.asyncio
async def test_router_emails_the_recipient():
    created = {"id": TRANSFER_ID, "status": "pending", "recipient_name": "Ravi", "seats": ["B4"]}
    tasks = BackgroundTasks()
    with patch.object(transfer_router.svc, "create_transfer", new=AsyncMock(return_value=created)):
        body = transfer_router.TransferCreate(booking_id=BOOKING_ID, seat_ids=[SEAT_A], recipient="x@y.com")
        result = await transfer_router.create_transfer(body, tasks, SENDER, make_conn())
    assert result["recipient_name"] == "Ravi"
    assert tasks.tasks[0].func is transfer_router.send_transfer_received_email


def test_emails_escape_user_text():
    transfer = {
        "sender_name": "<b>Asha</b>", "recipient_name": "Ravi", "event_title": "Hamlet & Co",
        "seats": ["B4"], "start_time": FUTURE, "venue_name": "NMS", "city": "Ahmedabad",
    }
    subject, body = build_received_email(transfer)
    assert "<b>Asha</b>" not in body and "&lt;b&gt;Asha" in body
    assert "/tickets/received" in body

    subject, body = build_response_email({**transfer, "status": "accepted", "booking_id": BOOKING_ID})
    assert "accepted" in subject and f"/bookings/{BOOKING_ID}" in body
