from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from routers.bookings import join_waitlist, leave_waitlist, list_my_waitlist

USER = {"id": "11111111-1111-1111-1111-111111111111"}
SHOW_ID = "22222222-2222-2222-2222-222222222222"
CREATED = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_conn(show=None, existing=None, entry=None, position=1, fetch_rows=None, execute_result="UPDATE 1"):
    conn = MagicMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx)
    # join_waitlist calls fetchrow for the show, then the existing entry, then the insert.
    conn.fetchrow = AsyncMock(side_effect=[show, existing, entry])
    conn.fetchval = AsyncMock(return_value=position)
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.execute = AsyncMock(return_value=execute_result)
    return conn


def sold_out_show():
    return {"id": SHOW_ID, "status": "scheduled", "event_status": "published",
            "available_seats": 0, "available_zone_capacity": 0}


@pytest.mark.asyncio
async def test_join_waitlist_on_sold_out_show_returns_position():
    conn = make_conn(show=sold_out_show(), existing=None,
                     entry={"id": "w1", "created_at": CREATED}, position=3)
    result = await join_waitlist(SHOW_ID, current_user=USER, conn=conn)
    assert result == {"status": "joined", "position": 3}
    insert_sql = conn.fetchrow.await_args_list[2].args[0]
    assert "INSERT INTO show_waitlist" in insert_sql


@pytest.mark.asyncio
async def test_join_waitlist_when_already_joined_returns_existing_position():
    conn = make_conn(show=sold_out_show(), existing={"id": "w1", "created_at": CREATED}, position=2)
    result = await join_waitlist(SHOW_ID, current_user=USER, conn=conn)
    assert result == {"status": "already_joined", "position": 2}
    assert conn.fetchrow.await_count == 2  # no insert attempted


@pytest.mark.asyncio
@pytest.mark.parametrize("seats,zones", [(5, 0), (0, 7), (3, 3)])
async def test_join_waitlist_rejects_show_that_is_not_sold_out(seats, zones):
    show = sold_out_show() | {"available_seats": seats, "available_zone_capacity": zones}
    conn = make_conn(show=show)
    with pytest.raises(HTTPException) as exc:
        await join_waitlist(SHOW_ID, current_user=USER, conn=conn)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("show", [
    None,
    {"id": SHOW_ID, "status": "cancelled", "event_status": "published",
     "available_seats": 0, "available_zone_capacity": 0},
    {"id": SHOW_ID, "status": "scheduled", "event_status": "draft",
     "available_seats": 0, "available_zone_capacity": 0},
])
async def test_join_waitlist_rejects_missing_or_unpublished_show(show):
    conn = make_conn(show=show)
    with pytest.raises(HTTPException) as exc:
        await join_waitlist(SHOW_ID, current_user=USER, conn=conn)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_leave_waitlist_cancels_active_entry():
    conn = make_conn(execute_result="UPDATE 1")
    result = await leave_waitlist(SHOW_ID, current_user=USER, conn=conn)
    assert result == {"status": "cancelled"}
    assert "status = 'cancelled'" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_leave_waitlist_without_active_entry_returns_404():
    conn = make_conn(execute_result="UPDATE 0")
    with pytest.raises(HTTPException) as exc:
        await leave_waitlist(SHOW_ID, current_user=USER, conn=conn)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_my_waitlist_returns_entries_with_position():
    rows = [{"id": "w1", "show_id": SHOW_ID, "created_at": CREATED, "event_title": "Movie A",
             "start_time": CREATED, "venue_name": "Venue A", "city": "Pune", "position": 2}]
    conn = make_conn(fetch_rows=rows)
    result = await list_my_waitlist(current_user=USER, conn=conn)
    assert result == rows
    assert conn.fetch.await_args.args[1] == USER["id"]


@pytest.mark.asyncio
async def test_list_my_waitlist_empty():
    conn = make_conn(fetch_rows=[])
    assert await list_my_waitlist(current_user=USER, conn=conn) == []
