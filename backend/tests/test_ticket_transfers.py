from datetime import datetime, timedelta, timezone
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from routers import ticket_transfers as transfer_router
from routers.tickets import TicketScanRequest, _scan_and_consume_ticket, scan_ticket
from services import ticket_transfer as svc
from services.transfer_email_service import (
    build_received_email,
    build_response_email,
    build_ticket_ready_email,
    ticket_pdf,
)

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
    conn.execute = AsyncMock(return_value="UPDATE 1")
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
    seat_insert = next(call for call in conn.execute.await_args_list if "INSERT INTO ticket_transfer_seats" in call.args[0])
    assert seat_insert.args[1:] == (TRANSFER_ID, [SEAT_A, SEAT_B])
    notification = next(call for call in conn.execute.await_args_list if "INSERT INTO notifications" in call.args[0])
    assert notification.args[1:3] == (FRIEND_ID, "transfer.received")
    assert json.loads(notification.args[3])["transfer_id"] == TRANSFER_ID


@pytest.mark.asyncio
async def test_cannot_transfer_someone_elses_booking():
    conn = make_conn(fetchrow=[None])
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A], "ravi@example.com")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_recipient_cannot_retransfer_a_received_ticket():
    # Only the original booking owner can create transfers, even after a recipient accepts.
    conn = make_conn(fetchrow=[None])
    with pytest.raises(svc.TransferError) as exc:
        await svc.create_transfer(conn, {"id": FRIEND_ID}, BOOKING_ID, [SEAT_A], "other@example.com")
    assert exc.value.status_code == 404
    assert conn.fetchrow.await_args.args[2] == FRIEND_ID


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
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
    result = await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=True)
    assert result["status"] == "accepted"
    update = next(call for call in conn.execute.await_args_list if "status = 'accepted'" in call.args[0])
    sql, tid, token = update.args
    assert "status = 'accepted'" in sql and tid == TRANSFER_ID
    assert len(token) >= 24
    notification = next(call for call in conn.execute.await_args_list if "INSERT INTO notifications" in call.args[0])
    assert notification.args[1:3] == (SENDER["id"], "transfer.accepted")
    assert json.loads(notification.args[3])["booking_id"] == BOOKING_ID


@pytest.mark.asyncio
async def test_decline():
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
    result = await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=False)
    assert result["status"] == "declined"
    assert any("status = 'declined'" in call.args[0] for call in conn.execute.await_args_list)
    notification = next(call for call in conn.execute.await_args_list if "INSERT INTO notifications" in call.args[0])
    assert notification.args[1:3] == (SENDER["id"], "transfer.declined")


@pytest.mark.asyncio
async def test_only_the_recipient_can_answer():
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
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
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row(**over)])
    with pytest.raises(svc.TransferError) as exc:
        await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=True)
    assert exc.value.status_code == 400
    assert not any("SET status = 'accepted'" in call.args[0] for call in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_accept_rejects_transfer_expiring_during_request():
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
    conn.execute.side_effect = ["UPDATE 0", "UPDATE 0"]
    with pytest.raises(svc.TransferError, match="expired"):
        await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=True)
    assert not any("INSERT INTO notifications" in call.args[0] for call in conn.execute.await_args_list)


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["decline", "cancel"])
async def test_response_rejects_transfer_expiring_during_request(action):
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
    conn.execute.side_effect = ["UPDATE 0", "UPDATE 0"]
    with pytest.raises(svc.TransferError, match="expired"):
        if action == "decline":
            await svc.respond_to_transfer(conn, FRIEND_ID, TRANSFER_ID, accept=False)
        else:
            await svc.cancel_transfer(conn, SENDER["id"], TRANSFER_ID)
    assert not any("INSERT INTO notifications" in call.args[0] for call in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_sender_cancels_pending_transfer():
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
    assert (await svc.cancel_transfer(conn, SENDER["id"], TRANSFER_ID))["status"] == "cancelled"
    notification = next(call for call in conn.execute.await_args_list if "INSERT INTO notifications" in call.args[0])
    assert notification.args[1:3] == (FRIEND_ID, "transfer.cancelled")


@pytest.mark.asyncio
async def test_accepted_transfer_cannot_be_cancelled():
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row(status="accepted")])
    with pytest.raises(svc.TransferError) as exc:
        await svc.cancel_transfer(conn, SENDER["id"], TRANSFER_ID)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_recipient_cannot_cancel_and_bad_id_is_404():
    conn = make_conn(fetchval=[BOOKING_ID, BOOKING_ID, TRANSFER_ID], fetchrow=[transfer_row()])
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
    conn = make_conn(fetch=[[received_row()], seats, [], []])
    [item] = await svc.list_received(conn, FRIEND_ID)
    assert item["qr_data"] == "TICKETFLOW-T:tok123"
    assert item["seats"] == ["B4"]

    conn = make_conn(fetch=[[received_row(status="pending", qr_token=None)], [], [], []])
    assert (await svc.list_received(conn, FRIEND_ID))[0]["qr_data"] is None

    conn = make_conn(fetch=[[received_row(booking_status="cancelled")], [], [], []])
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
    conn = make_conn(fetchrow=[scan_row()], fetchval=[TRANSFER_ID], fetch=[seats, []])
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
    conn = make_conn(fetchrow=[ticket], fetch=[seats, []], fetchval=[BOOKING_ID])
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


# ---------------------------------------------------------------------------
# Recipient's own ticket (PDF download + email after accepting)
# ---------------------------------------------------------------------------

def ticket_row(**over):
    row = {
        "id": TRANSFER_ID, "to_user_id": FRIEND_ID, "status": "accepted", "qr_token": "tok123",
        "booking_id": BOOKING_ID, "booking_status": "confirmed", "ticket_status": "valid",
        "event_title": "Hamlet", "start_time": FUTURE, "venue_name": "NMS Stage", "city": "Ahmedabad",
        "screen_name": "Main", "user_name": "Ravi", "user_email": "ravi@example.com", "sender_name": "Asha",
    }
    row.update(over)
    return row


TICKET_SEATS = [
    {"row_label": "B", "seat_number": 4, "seat_type": "standard", "price": 250},
    {"row_label": "B", "seat_number": 5, "seat_type": "standard", "price": 250},
]


@pytest.mark.asyncio
async def test_received_ticket_data_for_accepted_transfer():
    ticket = await svc.received_ticket_data(make_conn(fetchrow=[ticket_row()], fetch=[TICKET_SEATS, []]), FRIEND_ID, TRANSFER_ID)
    assert ticket["qr_data"] == "TICKETFLOW-T:tok123"
    assert ticket["total_amount"] == 500.0
    assert ticket["user_email"] == "ravi@example.com"
    assert "Asha" in ticket["user_name"]


@pytest.mark.asyncio
@pytest.mark.parametrize("user_id,over,status", [
    (SENDER["id"], {}, 404),                      # only the recipient
    (FRIEND_ID, {"status": "pending"}, 404),      # not accepted yet
    (FRIEND_ID, {"booking_status": "cancelled"}, 400),
])
async def test_received_ticket_data_rules(user_id, over, status):
    with pytest.raises(svc.TransferError) as exc:
        await svc.received_ticket_data(make_conn(fetchrow=[ticket_row(**over)], fetch=[TICKET_SEATS]), user_id, TRANSFER_ID)
    assert exc.value.status_code == status


def test_ticket_pdf_and_ready_email():
    ticket = {
        "booking_id": TRANSFER_ID, "event_title": "Hamlet", "venue_name": "NMS", "venue_city": "Ahmedabad",
        "screen_name": "Main", "start_time": FUTURE, "seats": TICKET_SEATS, "total_amount": 500.0,
        "user_name": "Ravi (from Asha)", "recipient_name": "Ravi", "sender_name": "<i>Asha</i>",
        "qr_data": "TICKETFLOW-T:tok123",
    }
    assert ticket_pdf(ticket).startswith(b"%PDF")
    subject, body = build_ticket_ready_email(ticket)
    assert "Hamlet" in subject and "B4, B5" in body
    assert "<i>Asha</i>" not in body


@pytest.mark.asyncio
async def test_pdf_route_returns_a_pdf():
    ticket = {"booking_id": TRANSFER_ID, "seats": [], "qr_data": "TICKETFLOW-T:tok123"}
    with patch.object(transfer_router.svc, "received_ticket_data", new=AsyncMock(return_value=ticket)):
        resp = await transfer_router.received_ticket_pdf(TRANSFER_ID, {"id": FRIEND_ID}, make_conn())
    assert resp.media_type == "application/pdf"


@pytest.mark.asyncio
async def test_accept_emails_the_recipient_their_ticket():
    tasks = BackgroundTasks()
    with patch.object(transfer_router.svc, "respond_to_transfer", new=AsyncMock(return_value={"status": "accepted"})), \
         patch.object(transfer_router.svc, "received_ticket_data", new=AsyncMock(return_value={"x": 1})):
        await transfer_router.accept_transfer(TRANSFER_ID, tasks, {"id": FRIEND_ID}, make_conn())
    funcs = [t.func for t in tasks.tasks]
    assert transfer_router.send_transfer_response_email in funcs
    assert transfer_router.send_ticket_ready_email in funcs


@pytest.mark.asyncio
async def test_decline_does_not_send_a_ticket():
    tasks = BackgroundTasks()
    with patch.object(transfer_router.svc, "respond_to_transfer", new=AsyncMock(return_value={"status": "declined"})):
        await transfer_router.decline_transfer(TRANSFER_ID, tasks, {"id": FRIEND_ID}, make_conn())
    assert [t.func for t in tasks.tasks] == [transfer_router.send_transfer_response_email, transfer_router.deliver_in_background]


@pytest.mark.asyncio
async def test_unknown_email_creates_unclaimed_invitation():
    conn = make_conn(fetchrow=[{"id": BOOKING_ID}, booking_row()], fetch=[[], FREE_SEATS], fetchval=[TRANSFER_ID])
    result = await svc.create_transfer(conn, SENDER, BOOKING_ID, [SEAT_A, SEAT_B], "new@example.com")
    assert result["invited"] is True
    assert result["recipient_email"] == "new@example.com"
    assert conn.fetchval.await_args.args[3] is None
    assert not any("INSERT INTO notifications" in c.args[0] for c in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_only_verified_firebase_email_claims_invites():
    from fastapi.security import HTTPAuthorizationCredentials
    conn = make_conn(fetch=[[]])
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="example-token")
    with patch.object(transfer_router, "verify_firebase_token", return_value={"email": "friend@example.com", "email_verified": False}):
        await transfer_router.received_transfers(user={"id": FRIEND_ID, "email": "friend@example.com"}, conn=conn, credentials=token)
    assert not any("SET to_user_id" in c.args[0] for c in conn.execute.await_args_list)
    conn = make_conn(fetch=[[]])
    with patch.object(transfer_router, "verify_firebase_token", return_value={"email": "friend@example.com", "email_verified": True}):
        await transfer_router.received_transfers(user={"id": FRIEND_ID, "email": "friend@example.com"}, conn=conn, credentials=token)
    claim = next(c for c in conn.execute.await_args_list if "SET to_user_id" in c.args[0])
    assert claim.args[1:] == (FRIEND_ID, "friend@example.com")
    assert "tt.status = 'pending'" in claim.args[0]
    assert "24 hours" in claim.args[0]


@pytest.mark.asyncio
async def test_invitation_not_claimed_when_profile_email_differs_from_firebase():
    from fastapi.security import HTTPAuthorizationCredentials
    conn = make_conn(fetch=[[]])
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="example-token")
    with patch.object(transfer_router, "verify_firebase_token", return_value={"email": "friend@example.com", "email_verified": True}):
        await transfer_router.received_transfers(user={"id": FRIEND_ID, "email": "other@example.com"}, conn=conn, credentials=token)
    assert not any("SET to_user_id" in c.args[0] for c in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_zone_availability_subtracts_active_allocations():
    conn = make_conn(fetch=[[{"id": SEAT_A, "name": "Standing", "quantity": 5, "allocated": 2}]])
    result = await svc.available_zone_quantities(conn, BOOKING_ID)
    assert result == [{"booking_zone_id": SEAT_A, "name": "Standing", "quantity": 5, "available": 3}]
    query = conn.fetch.await_args.args[0]
    assert "tt.status IN ('pending', 'accepted')" in query


@pytest.mark.asyncio
async def test_original_qr_zone_count_excludes_only_accepted_transfers():
    conn = make_conn(fetch=[[{"id": SEAT_A, "name": "Standing", "quantity": 5, "transferred": 2, "unit_price": 100}]])
    result = await svc.zones_left_on_booking(conn, BOOKING_ID)
    assert result == [{"booking_zone_id": SEAT_A, "name": "Standing", "quantity": 3, "unit_price": 100}]
    assert "tt.status = 'accepted'" in conn.fetch.await_args.args[0]

@pytest.mark.asyncio
async def test_zone_transfer_reserves_requested_quantity():
    zone_id = "88888888-8888-8888-8888-888888888888"
    conn = make_conn(fetchrow=[{"id": BOOKING_ID}, booking_row()],
                     fetch=[[FRIEND], [], [{"id": zone_id, "name": "Standing", "quantity": 5, "allocated": 2}]],
                     fetchval=[TRANSFER_ID])
    result = await svc.create_transfer(conn, SENDER, BOOKING_ID, [], "ravi@example.com",
                                       [{"booking_zone_id": zone_id, "quantity": 3}])
    assert result["seats"] == ["Standing × 3"]
    assert any("INSERT INTO ticket_transfer_zones" in call.args[0] and call.args[1:] == (TRANSFER_ID, zone_id, 3)
               for call in conn.execute.await_args_list)


@pytest.mark.asyncio
async def test_zone_transfer_rejects_overallocation():
    zone_id = "88888888-8888-8888-8888-888888888888"
    conn = make_conn(fetchrow=[{"id": BOOKING_ID}, booking_row()],
                     fetch=[[FRIEND], [], [{"id": zone_id, "name": "Standing", "quantity": 5, "allocated": 3}]])
    with pytest.raises(svc.TransferError, match="unavailable"):
        await svc.create_transfer(conn, SENDER, BOOKING_ID, [], "ravi@example.com",
                                  [{"booking_zone_id": zone_id, "quantity": 3}])
    assert not any("INSERT INTO ticket_transfers " in call.args[0] for call in conn.fetchval.await_args_list)


@pytest.mark.asyncio
async def test_cancelled_transfer_stays_visible_without_qr():
    conn = make_conn(fetch=[[received_row(status="cancelled", qr_token=None)], [], [], []])
    [item] = await svc.list_received(conn, FRIEND_ID)
    assert item["status"] == "cancelled"
    assert item["qr_data"] is None
    assert "status <> 'cancelled'" not in conn.fetch.await_args_list[0].args[0]
