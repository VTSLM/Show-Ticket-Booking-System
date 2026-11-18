"""
Tests for issue #80: the manager API must only let a manager see and change
their own organization's venues, events, shows and zones. Admins keep access
to everything. Rows a manager does not own answer 404.

The ownership queries return 1 when the row belongs to the caller, so a mock
fetchval returning None stands in for "owned by another organization".
"""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from routers import manager as m


def _user(*roles):
    return {"id": str(uuid.uuid4()), "roles": list(roles)}


def _not_owned():
    conn = AsyncMock()
    conn.fetchval.return_value = None
    return conn


def _owned():
    conn = AsyncMock()
    conn.fetchval.return_value = 1
    return conn


def _id():
    return str(uuid.uuid4())


def test_every_manager_endpoint_requires_a_manager_or_admin_login():
    for route in m.router.routes:
        if not isinstance(route, APIRoute):
            continue
        calls = [d.call for d in route.dependant.dependencies]
        assert m.MANAGER_ROLES in calls, f"{route.methods} {route.path} has no login check"


# Each call is made by a manager who does not own the target row.
FOREIGN_CALLS = [
    ("update event", lambda u, c: m.update_event(event_id=_id(), body={"title": "x"}, user=u, conn=c)),
    ("delete event", lambda u, c: m.delete_event(event_id=_id(), user=u, conn=c)),
    ("get show", lambda u, c: m.get_show(show_id=_id(), user=u, conn=c)),
    ("update show", lambda u, c: m.update_show(show_id=_id(), body={"base_price": 1}, user=u, conn=c)),
    ("delete show", lambda u, c: m.delete_show(show_id=_id(), user=u, conn=c)),
    ("list zones", lambda u, c: m.list_show_zones(show_id=_id(), user=u, conn=c)),
    ("add zone", lambda u, c: m.add_show_zone(
        show_id=_id(), body=m.ZoneInput(name="GA", total_capacity=1, price=1), user=u, conn=c)),
    ("delete zone", lambda u, c: m.delete_show_zone(show_id=_id(), zone_id=_id(), user=u, conn=c)),
    ("add screen", lambda u, c: m.create_screen(
        venue_id=_id(), body=m.ScreenCreate(name="S", capacity=1), user=u, conn=c)),
    ("seat tiers", lambda u, c: m.update_seat_tier(
        screen_id=_id(), body=m.UpdateSeatTierRequest(row_label="A"), user=u, conn=c)),
    ("list screens", lambda u, c: m.list_screens(venue_id=_id(), user=u, conn=c)),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("name,call", FOREIGN_CALLS, ids=[n for n, _ in FOREIGN_CALLS])
async def test_manager_gets_404_for_another_organizations_row(name, call):
    conn = _not_owned()
    with pytest.raises(HTTPException) as exc:
        await call(_user("manager"), conn)
    assert exc.value.status_code == 404
    # Nothing was read beyond the ownership check, and nothing was changed.
    conn.execute.assert_not_awaited()
    conn.executemany.assert_not_awaited()
    conn.fetch.assert_not_awaited()
    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_ids_answer_404_without_querying():
    conn = _owned()
    with pytest.raises(HTTPException) as exc:
        await m.delete_show(show_id="not-a-uuid", user=_user("manager"), conn=conn)
    assert exc.value.status_code == 404
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_can_delete_own_show():
    conn = _owned()
    show_id = _id()
    await m.delete_show(show_id=show_id, user=_user("manager"), conn=conn)
    conn.execute.assert_awaited_once()
    assert conn.execute.await_args.args[1] == show_id


@pytest.mark.asyncio
async def test_admin_skips_ownership_checks():
    conn = AsyncMock()
    await m.delete_event(event_id=_id(), user=_user("admin"), conn=conn)
    conn.fetchval.assert_not_awaited()
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_event_and_show_lists_are_filtered_for_managers():
    manager = _user("manager")
    for list_fn in (m.list_events, m.list_shows):
        conn = AsyncMock()
        conn.fetch.return_value = []
        await list_fn(user=manager, conn=conn)
        sql, is_admin, user_id = conn.fetch.await_args.args
        assert is_admin is False and user_id == manager["id"]
        assert "organizer_profiles" in sql or "op.user_id" in sql


@pytest.mark.asyncio
async def test_admin_lists_are_unfiltered():
    conn = AsyncMock()
    conn.fetch.return_value = []
    await m.list_events(user=_user("admin"), conn=conn)
    assert conn.fetch.await_args.args[1] is True


@pytest.mark.asyncio
async def test_manager_venue_list_is_own_plus_approved():
    conn = AsyncMock()
    conn.fetch.return_value = []
    manager = _user("manager")
    await m.list_venues(user=manager, conn=conn)
    sql, user_id = conn.fetch.await_args.args
    assert user_id == manager["id"]
    assert "venue_verification_cases" in sql and "'approved'" in sql


@pytest.mark.asyncio
async def test_manager_cannot_schedule_show_for_another_organizations_event():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "event_title": "Someone Else's Fest",
        "organizer_id": _id(),
        "org_user_id": _id(),  # not the caller
        "org_name": "Org B",
        "org_status": "APPROVED",
        "venue_name": "Arena",
        "venue_status": "approved",
    }
    body = m.ShowCreate(
        event_id=_id(), screen_id=_id(),
        start_time="2026-12-01T18:00:00+05:30", end_time="2026-12-01T21:00:00+05:30",
        base_price=200,
    )
    with pytest.raises(HTTPException) as exc:
        await m.create_show(body=body, user=_user("manager"), conn=conn)
    assert exc.value.status_code == 404
    assert conn.fetchrow.await_count == 1  # the INSERT never ran
    conn.execute.assert_not_awaited()
