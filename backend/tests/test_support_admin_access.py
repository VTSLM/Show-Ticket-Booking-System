"""The support inbox (/api/admin/support) is for admins only."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_conn
from dependencies import get_current_user
from routers.support_admin import router

REQUEST_ID = "408e08d1-d2f6-4d0f-a9cb-b295f70a7b45"
MANAGER = {"id": "11111111-1111-1111-1111-111111111111", "roles": ["manager"], "status": "active"}
CUSTOMER = {"id": "22222222-2222-2222-2222-222222222222", "roles": ["customer"], "status": "active"}
ADMIN = {"id": "33333333-3333-3333-3333-333333333333", "roles": ["admin"], "status": "active"}

ENDPOINTS = [
    ("get", "/api/admin/support/requests", None),
    ("get", f"/api/admin/support/requests/{REQUEST_ID}", None),
    ("post", f"/api/admin/support/requests/{REQUEST_ID}/reply", {"message": "Hello there"}),
    ("patch", f"/api/admin/support/requests/{REQUEST_ID}/status", {"status": "closed"}),
]


def make_client(user):
    app = FastAPI()
    app.include_router(router)
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock()

    async def _conn():
        yield conn

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), conn


@pytest.mark.parametrize("user", [MANAGER, CUSTOMER], ids=["manager", "customer"])
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_non_admins_are_refused(user, method, path, body):
    client, conn = make_client(user)
    r = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
    assert r.status_code == 403
    conn.fetch.assert_not_called()
    conn.fetchrow.assert_not_called()


def test_admin_can_list_requests():
    client, _ = make_client(ADMIN)
    r = client.get("/api/admin/support/requests")
    assert r.status_code == 200
