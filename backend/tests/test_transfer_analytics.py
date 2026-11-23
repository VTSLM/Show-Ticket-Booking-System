from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.manager_analytics import transfer_statistics


@pytest.mark.asyncio
async def test_transfer_statistics_are_scoped_to_manager():
    conn = AsyncMock()
    conn.fetch.return_value = [{"status": "accepted", "count": 2}, {"status": "pending", "count": 1}]
    result = await transfer_statistics(days=30, start=date(2026, 1, 1), end=date(2026, 1, 31),
                                       event_id=None, user={"id": "manager-id", "roles": ["manager"]}, conn=conn)
    assert result["total"] == 3
    assert result["statuses"]["expired"] == 0
    assert conn.fetch.await_args.args[1:] == ("manager-id", None, date(2026, 1, 1), date(2026, 1, 31))


@pytest.mark.asyncio
async def test_transfer_statistics_admin_can_see_all_and_rejects_invalid_event():
    conn = AsyncMock()
    conn.fetch.return_value = []
    await transfer_statistics(days=30, start=None, end=None, event_id=None,
                              user={"id": "admin-id", "roles": ["admin"]}, conn=conn)
    assert conn.fetch.await_args.args[1] is None
    with pytest.raises(HTTPException) as error:
        await transfer_statistics(days=30, start=None, end=None, event_id="invalid",
                                  user={"id": "admin-id", "roles": ["admin"]}, conn=conn)
    assert error.value.status_code == 400



@pytest.mark.asyncio
async def test_admin_transfer_list_requires_admin_role():
    from dependencies import get_current_user
    from routers.ticket_transfers import router

    route = next(r for r in router.routes if r.path == "/api/transfers/admin")
    role_guard = next(d.call for d in route.dependant.dependencies
                      if any(child.call is get_current_user for child in d.dependencies))
    with pytest.raises(HTTPException) as error:
        await role_guard({"id": "manager", "roles": ["manager"]})
    assert error.value.status_code == 403
    assert await role_guard({"id": "admin", "roles": ["admin"]})


@pytest.mark.asyncio
async def test_admin_transfer_list_paginates():
    from routers.ticket_transfers import admin_transfers

    conn = AsyncMock()
    conn.fetchval.return_value = 26
    conn.fetch.return_value = [{"id": "transfer-id", "status": "accepted"}]
    result = await admin_transfers(page=2, page_size=25, _={"roles": ["admin"]}, conn=conn)
    assert result["total"] == 26
    assert result["transfers"][0]["status"] == "accepted"
    assert conn.fetch.await_args.args[1:] == (25, 25)
