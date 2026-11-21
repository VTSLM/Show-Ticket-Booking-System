"""#174: bookings store their price breakdown, and every query uses all its parameters."""
import re
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from routers import bookings
from routers.bookings import CreateBookingRequest

USER_ID = str(uuid.uuid4())
SHOW_ID = str(uuid.uuid4())
ZONE_ID = str(uuid.uuid4())


def make_conn():
    conn = MagicMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock(return_value=uuid.uuid4())
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.transaction = MagicMock(return_value=AsyncMock())
    return conn


def all_calls(conn):
    return [c for m in (conn.fetch, conn.fetchrow, conn.fetchval, conn.execute) for c in m.await_args_list]


def booking_insert(conn):
    calls = [c for c in conn.fetchval.await_args_list if "INSERT INTO bookings" in c.args[0]]
    assert len(calls) == 1
    return calls[0]


def assert_every_placeholder_matches(conn):
    """Postgres rejects a statement that passes a parameter it never uses ($2 with no $2)."""
    for call in all_calls(conn):
        sql, args = call.args[0], call.args[1:]
        used = {int(n) for n in re.findall(r"\$(\d+)", sql)}
        assert used == set(range(1, len(args) + 1)), sql


def locked_seats(*prices):
    return [
        {"id": uuid.uuid4(), "price": Decimal(p), "status": "locked", "locked_by": uuid.UUID(USER_ID)}
        for p in prices
    ]


@pytest.mark.asyncio
async def test_seat_booking_stores_subtotal_discount_and_total():
    conn = make_conn()
    seats = locked_seats("300.00", "300.00")
    conn.fetch.return_value = seats
    req = CreateBookingRequest(show_id=SHOW_ID, seat_ids=[str(s["id"]) for s in seats])

    result = await bookings.create_booking(req, current_user={"id": USER_ID}, conn=conn)

    insert = booking_insert(conn)
    assert "subtotal_amount" in insert.args[0] and "discount_amount" in insert.args[0]
    subtotal, discount, coupon_id, total = insert.args[4:8]
    assert (subtotal, discount, total) == (Decimal("600.00"), Decimal("0"), Decimal("600.00"))
    assert coupon_id is None
    assert result["total_amount"] == 600.0
    assert_every_placeholder_matches(conn)


@pytest.mark.asyncio
async def test_free_seat_booking_stores_zero_amounts():
    conn = make_conn()
    seats = locked_seats("0.00")
    conn.fetch.return_value = seats
    req = CreateBookingRequest(show_id=SHOW_ID, seat_ids=[str(seats[0]["id"])])

    result = await bookings.create_booking(req, current_user={"id": USER_ID}, conn=conn)

    assert booking_insert(conn).args[4:8] == (
        Decimal("0"),
        Decimal("0"),
        None,
        Decimal("0"),
    )
    assert result["total_amount"] == 0.0


@pytest.mark.asyncio
async def test_zone_booking_stores_amounts_and_checks_the_show():
    conn = make_conn()
    conn.fetchrow.return_value = {"id": uuid.UUID(ZONE_ID), "name": "Fan Pit", "price": Decimal("8500.00")}
    req = CreateBookingRequest(show_id=SHOW_ID, zone_id=ZONE_ID, zone_quantity=2)

    result = await bookings.create_booking(req, current_user={"id": USER_ID}, conn=conn)

    assert booking_insert(conn).args[4:8] == (
        Decimal("17000.00"),
        Decimal("0"),
        None,
        Decimal("17000.00"),
    )
    assert result["total_amount"] == 17000.0
    update = next(c for c in conn.execute.await_args_list if "UPDATE show_zones" in c.args[0])
    assert "show_id=$2::uuid" in update.args[0]
    assert_every_placeholder_matches(conn)


@pytest.mark.asyncio
async def test_zone_booking_refused_when_sold_out():
    conn = make_conn()
    conn.fetchrow.return_value = {"id": uuid.UUID(ZONE_ID), "name": "Fan Pit", "price": Decimal("100")}
    conn.execute.return_value = "UPDATE 0"
    req = CreateBookingRequest(show_id=SHOW_ID, zone_id=ZONE_ID, zone_quantity=2)

    with pytest.raises(bookings.HTTPException) as exc:
        await bookings.create_booking(req, current_user={"id": USER_ID}, conn=conn)
    assert exc.value.status_code == 409
    assert not [c for c in conn.fetchval.await_args_list if "INSERT INTO bookings" in c.args[0]]
