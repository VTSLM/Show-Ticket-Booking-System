from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.manager_analytics import event_analytics, manager_analytics
from services.manager_analytics import _pct_change, build_overview, resolve_range

MANAGER_ID = "11111111-1111-1111-1111-111111111111"
EVENT_ID = "22222222-2222-2222-2222-222222222222"
TODAY = date(2026, 11, 17)


class ZeroRow(dict):
    """asyncpg-like row where every column is 0 (an organization with no sales yet)."""

    def __missing__(self, key):
        return 0


def make_user(roles):
    return {"id": MANAGER_ID, "name": "Test", "email": "t@example.com", "roles": roles}


def empty_conn(has_org=True):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=ZeroRow())
    conn.fetchval = AsyncMock(return_value=1 if has_org else None)
    return conn


# ---------------------------------------------------------------------------
# Date range and helpers
# ---------------------------------------------------------------------------

def test_resolve_range_last_n_days_includes_today():
    assert resolve_range(30, None, None, today=TODAY) == (date(2026, 10, 19), TODAY)
    assert resolve_range(1, None, None, today=TODAY) == (TODAY, TODAY)


def test_resolve_range_custom_dates():
    assert resolve_range(30, date(2026, 9, 1), date(2026, 9, 30)) == (date(2026, 9, 1), date(2026, 9, 30))


@pytest.mark.parametrize("start,end,message", [
    (date(2026, 9, 1), None, "Give both start and end dates"),
    (None, date(2026, 9, 1), "Give both start and end dates"),
    (date(2026, 9, 30), date(2026, 9, 1), "End date must be on or after start date"),
    (date(2023, 1, 1), date(2026, 1, 1), "Date range can be at most 2 years"),
])
def test_resolve_range_rejects_bad_custom_ranges(start, end, message):
    with pytest.raises(ValueError, match=message):
        resolve_range(30, start, end)


def test_pct_change():
    assert _pct_change(150, 100) == 50.0
    assert _pct_change(50, 100) == -50.0
    assert _pct_change(10, 0) is None  # no previous period to compare with


# ---------------------------------------------------------------------------
# Overview endpoint: access and validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_sees_only_own_organization():
    conn = empty_conn()
    with patch("routers.manager_analytics.build_overview", new=AsyncMock(return_value={})) as build:
        await manager_analytics(days=30, start=None, end=None, event_id=None,
                                user=make_user(["manager"]), conn=conn)
    owner = build.await_args.args[1]
    assert owner == MANAGER_ID
    assert build.await_args.kwargs["has_org"] is True


@pytest.mark.asyncio
async def test_admin_sees_all_organizations():
    conn = empty_conn()
    with patch("routers.manager_analytics.build_overview", new=AsyncMock(return_value={})) as build:
        await manager_analytics(days=30, start=None, end=None, event_id=None,
                                user=make_user(["manager", "admin"]), conn=conn)
    assert build.await_args.args[1] is None  # no owner filter
    conn.fetchval.assert_not_awaited()       # admins skip the organization lookup


@pytest.mark.asyncio
async def test_manager_without_organization_is_flagged():
    conn = empty_conn(has_org=False)
    with patch("routers.manager_analytics.build_overview", new=AsyncMock(return_value={})) as build:
        await manager_analytics(days=30, start=None, end=None, event_id=None,
                                user=make_user(["manager"]), conn=conn)
    assert build.await_args.kwargs["has_org"] is False


@pytest.mark.asyncio
async def test_invalid_event_id_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await manager_analytics(days=30, start=None, end=None, event_id="not-a-uuid",
                                user=make_user(["manager"]), conn=empty_conn())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_bad_custom_range_returns_400():
    with pytest.raises(HTTPException) as exc:
        await manager_analytics(days=30, start=date(2026, 9, 30), end=date(2026, 9, 1), event_id=None,
                                user=make_user(["manager"]), conn=empty_conn())
    assert exc.value.status_code == 400
    assert "End date" in exc.value.detail


# ---------------------------------------------------------------------------
# Overview calculations with no data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overview_with_no_sales_returns_zeroes():
    conn = empty_conn()
    data = await build_overview(conn, MANAGER_ID, None, date(2026, 11, 11), TODAY)

    assert data["scope"] == "your organization"
    assert data["range"] == {"start": "2026-11-11", "end": "2026-11-17", "days": 7,
                             "previous_start": "2026-11-04", "previous_end": "2026-11-10"}
    summary = data["summary"]
    assert summary["revenue"] == 0
    assert summary["tickets_sold"] == 0
    assert summary["revenue_change_pct"] is None
    assert summary["occupancy_pct"] is None
    assert data["trend"] == []  # one row per day comes from SQL generate_series
    assert [d["day"] for d in data["by_weekday"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert len(data["by_time_slot"]) == 4
    assert data["upcoming_shows"] == []

    # every query is scoped to the manager's own organization ($1 = owner)
    for call in conn.fetch.await_args_list + conn.fetchrow.await_args_list:
        if "my_events" in call.args[0]:
            assert call.args[1] == MANAGER_ID


@pytest.mark.asyncio
async def test_overview_scope_for_admin():
    data = await build_overview(empty_conn(), None, None, TODAY, TODAY)
    assert data["scope"] == "all organizations"


# ---------------------------------------------------------------------------
# Per-event endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_detail_invalid_id_is_404():
    with pytest.raises(HTTPException) as exc:
        await event_analytics(event_id="nope", days=30, start=None, end=None,
                              user=make_user(["manager"]), conn=empty_conn())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_event_of_another_organization_is_404():
    conn = empty_conn()
    conn.fetchrow = AsyncMock(return_value=None)  # event not visible to this manager
    with pytest.raises(HTTPException) as exc:
        await event_analytics(event_id=EVENT_ID, days=30, start=None, end=None,
                              user=make_user(["manager"]), conn=conn)
    assert exc.value.status_code == 404
    assert conn.fetchrow.await_args.args[1:] == (MANAGER_ID, EVENT_ID)


@pytest.mark.asyncio
async def test_event_detail_returned_for_own_event():
    detail = {"event": {"id": EVENT_ID}}
    with patch("routers.manager_analytics.build_event_detail", new=AsyncMock(return_value=detail)) as build:
        result = await event_analytics(event_id=EVENT_ID, days=30, start=None, end=None,
                                       user=make_user(["manager"]), conn=empty_conn())
    assert result == detail
    assert build.await_args.args[1:3] == (MANAGER_ID, EVENT_ID)
