"""
Tests for issue #109: creating a venue failed for everyone, and admins were
treated as managers.

get_current_user returns roles as a list ({"roles": ["admin"]}), never a
single "role" key, so these tests build users the same way.
"""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from routers.manager import (
    EventCreate,
    ShowCreate,
    VenueCreate,
    _is_admin,
    create_event,
    create_show,
    create_venue,
)


def _conn():
    conn = AsyncMock()

    @asynccontextmanager
    async def _tx():
        yield

    conn.transaction = MagicMock(side_effect=_tx)
    return conn


def _user(*roles):
    return {"id": str(uuid.uuid4()), "roles": list(roles)}


def test_is_admin_reads_roles_list():
    assert _is_admin({"roles": ["admin"]})
    assert _is_admin({"roles": ["manager", "admin"]})
    assert not _is_admin({"roles": ["manager"]})
    assert not _is_admin({"roles": None})
    assert not _is_admin({"role": "admin"})  # the old, never-set key


@pytest.mark.asyncio
async def test_manager_creates_unverified_venue_with_draft_case():
    conn = _conn()
    venue_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {"id": venue_id, "verification_status": "unverified"}
    manager = _user("manager")

    res = await create_venue(body=VenueCreate(name="Ravi Hall", city="Ahmedabad"), user=manager, conn=conn)

    assert res["id"] == venue_id
    assert conn.fetchrow.await_args.args[-1] == "unverified"

    # A verification case is opened, and it relies on the column default
    # ('draft'). The old code sent 'DRAFT', which the check constraint rejects.
    conn.execute.assert_awaited_once()
    sql, *params = conn.execute.await_args.args
    assert "venue_verification_cases" in sql
    assert "DRAFT" not in sql
    assert params == [venue_id, manager["id"]]


@pytest.mark.asyncio
async def test_admin_creates_approved_venue_without_case():
    conn = _conn()
    conn.fetchrow.return_value = {"id": str(uuid.uuid4()), "verification_status": "approved"}

    await create_venue(body=VenueCreate(name="Admin Arena", city="Surat"), user=_user("admin"), conn=conn)

    assert conn.fetchrow.await_args.args[-1] == "approved"
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_creates_event_without_organizer_profile():
    conn = _conn()
    event_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {"id": event_id, "title": "Admin Showcase"}

    res = await create_event(body=EventCreate(title="Admin Showcase"), user=_user("admin"), conn=conn)

    assert res["id"] == event_id
    conn.fetch.assert_not_awaited()  # no organizer lookup for admins


@pytest.mark.asyncio
async def test_admin_creates_show_without_verification_guards():
    conn = _conn()
    show_id = str(uuid.uuid4())
    conn.fetchrow.return_value = {"id": show_id}
    body = ShowCreate(
        event_id=str(uuid.uuid4()),
        screen_id=str(uuid.uuid4()),
        start_time="2026-12-01T18:00:00+05:30",
        end_time="2026-12-01T21:00:00+05:30",
        base_price=250,
    )

    res = await create_show(body=body, user=_user("admin"), conn=conn)

    assert res["id"] == show_id
    # Only the INSERT ran; the organizer/venue guard query was skipped.
    assert conn.fetchrow.await_count == 1
    assert "INSERT INTO shows" in conn.fetchrow.await_args.args[0]
