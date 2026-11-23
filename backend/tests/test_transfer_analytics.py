from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


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
