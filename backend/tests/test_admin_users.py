"""Admin user management (#138): access rules, safety rules and audit logging."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from database import get_conn
from dependencies import get_current_user
from routers import admin_users as admin_users_router
from routers import auth as auth_router_module
from services import admin_users

ADMIN = {"id": "11111111-1111-1111-1111-111111111111", "roles": ["admin"], "status": "active"}
MANAGER = {"id": "22222222-2222-2222-2222-222222222222", "roles": ["manager"], "status": "active"}
CUSTOMER = {"id": "33333333-3333-3333-3333-333333333333", "roles": ["customer"], "status": "active"}
TARGET_ID = "44444444-4444-4444-4444-444444444444"
NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def user_row(status="active", user_id=TARGET_ID):
    return {
        "id": uuid.UUID(user_id), "firebase_uid": "fb-target", "name": "Target",
        "email": "target@example.com", "phone": None, "status": status, "created_at": NOW,
    }


def roles_rows(*codes):
    return [{"code": c} for c in codes]


def make_conn():
    conn = MagicMock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.transaction = MagicMock(return_value=AsyncMock())
    return conn


def executed_sql(conn):
    return [call.args[0] for call in conn.execute.await_args_list]


def audit_call(conn):
    calls = [c for c in conn.execute.await_args_list if "INSERT INTO admin_audit_log" in c.args[0]]
    assert len(calls) == 1, "exactly one audit row per change"
    return calls[0].args


# ── HTTP layer: who may call what ───────────────────────────────────────────

ENDPOINTS = [
    ("get", "/api/admin/users", None),
    ("get", f"/api/admin/users/{TARGET_ID}", None),
    ("patch", f"/api/admin/users/{TARGET_ID}/roles", {"role": "manager", "action": "add", "reason": "Runs events"}),
    ("patch", f"/api/admin/users/{TARGET_ID}/status", {"status": "blocked", "reason": "Abuse"}),
]


def make_client(user, monkeypatch=None):
    app = FastAPI()
    app.include_router(admin_users_router.router)
    conn = make_conn()

    async def _conn():
        yield conn

    app.dependency_overrides[get_conn] = _conn
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), conn


@pytest.mark.parametrize("user", [MANAGER, CUSTOMER], ids=["manager", "customer"])
@pytest.mark.parametrize("method,path,body", ENDPOINTS)
def test_non_admins_get_403_and_touch_nothing(user, method, path, body):
    client, conn = make_client(user)
    call = getattr(client, method)
    r = call(path, json=body) if body else call(path)
    assert r.status_code == 403
    conn.fetchrow.assert_not_called()
    conn.fetch.assert_not_called()
    conn.execute.assert_not_called()


@pytest.mark.parametrize("body", [
    {"role": "manager", "action": "add"},                       # no reason
    {"role": "manager", "action": "add", "reason": "   no"},    # too short once trimmed
    {"role": "customer", "action": "add", "reason": "Because"}, # customer is not manageable
    {"role": "manager", "action": "promote", "reason": "Because"},
])
def test_role_change_validates_the_body(body):
    client, conn = make_client(ADMIN)
    r = client.patch(f"/api/admin/users/{TARGET_ID}/roles", json=body)
    assert r.status_code == 422
    conn.execute.assert_not_called()


@pytest.mark.parametrize("body", [
    {"status": "blocked"},
    {"status": "inactive", "reason": "Pending again"},
    {"status": "blocked", "reason": "x" * 501},
])
def test_status_change_validates_the_body(body):
    client, conn = make_client(ADMIN)
    r = client.patch(f"/api/admin/users/{TARGET_ID}/status", json=body)
    assert r.status_code == 422
    conn.execute.assert_not_called()


@pytest.mark.parametrize("query", ["page=0", "page_size=101", "role=critic", "status=deleted", "q=" + "a" * 101])
def test_list_validates_the_query(query):
    client, _ = make_client(ADMIN)
    assert client.get(f"/api/admin/users?{query}").status_code == 422


def test_blocking_revokes_firebase_sessions_after_the_response(monkeypatch):
    client, _ = make_client(ADMIN)
    monkeypatch.setattr(admin_users, "change_status",
                        AsyncMock(return_value=({"id": TARGET_ID, "status": "blocked"}, "fb-target")))
    revoke = AsyncMock()
    monkeypatch.setattr(admin_users, "revoke_sessions", revoke)
    r = client.patch(f"/api/admin/users/{TARGET_ID}/status", json={"status": "blocked", "reason": "Abuse"})
    assert r.status_code == 200 and r.json()["status"] == "blocked"
    revoke.assert_awaited_once_with("fb-target")


def test_unblocking_does_not_revoke_sessions(monkeypatch):
    client, _ = make_client(ADMIN)
    monkeypatch.setattr(admin_users, "change_status",
                        AsyncMock(return_value=({"id": TARGET_ID, "status": "active"}, None)))
    revoke = AsyncMock()
    monkeypatch.setattr(admin_users, "revoke_sessions", revoke)
    r = client.patch(f"/api/admin/users/{TARGET_ID}/status", json={"status": "active", "reason": "Appeal accepted"})
    assert r.status_code == 200
    revoke.assert_not_awaited()


# ── Listing ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_users_escapes_wildcards_and_pages():
    conn = make_conn()
    conn.fetchval.return_value = 41
    conn.fetch.return_value = [{**user_row(), "roles": ["manager", "customer"]}]
    result = await admin_users.list_users(conn, " 50%_off ", "manager", "active", page=3, page_size=20)

    count_args = conn.fetchval.await_args.args
    assert count_args[1:] == ("%50\\%\\_off%", "active", "manager")
    list_args = conn.fetch.await_args.args
    assert list_args[1:] == ("%50\\%\\_off%", "active", "manager", 20, 40)
    assert result["total"] == 41 and result["page"] == 3 and result["page_size"] == 20
    assert result["users"][0]["roles"] == ["customer", "manager"]
    assert result["users"][0]["id"] == TARGET_ID
    assert "firebase_uid" not in result["users"][0]


@pytest.mark.asyncio
async def test_list_users_without_filters_passes_nulls():
    conn = make_conn()
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []
    result = await admin_users.list_users(conn, "  ", None, None, page=1, page_size=25)
    assert conn.fetch.await_args.args[1:] == (None, None, None, 25, 0)
    assert result == {"users": [], "total": 0, "page": 1, "page_size": 25}


@pytest.mark.asyncio
async def test_get_user_includes_history_and_hides_firebase_uid():
    conn = make_conn()
    conn.fetchrow.return_value = user_row()
    conn.fetch.side_effect = [
        roles_rows("customer"),
        [{"id": uuid.uuid4(), "action": "status_changed", "details": json.dumps({"from": "active", "to": "blocked"}),
          "reason": "Abuse", "created_at": NOW, "admin_name": "Admin", "admin_email": "a@x.com"}],
    ]
    user = await admin_users.get_user(conn, TARGET_ID)
    assert "firebase_uid" not in user
    assert user["history"][0]["details"] == {"from": "active", "to": "blocked"}


@pytest.mark.asyncio
async def test_get_unknown_user_returns_404():
    conn = make_conn()
    conn.fetchrow.return_value = None
    with pytest.raises(HTTPException) as exc:
        await admin_users.get_user(conn, TARGET_ID)
    assert exc.value.status_code == 404


# ── Roles ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_cannot_change_own_roles():
    conn = make_conn()
    with pytest.raises(HTTPException) as exc:
        await admin_users.change_role(conn, ADMIN, ADMIN["id"], "admin", "remove", "Stepping down")
    assert exc.value.status_code == 400
    conn.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_adding_the_manager_role_is_audited():
    conn = make_conn()
    conn.fetchrow.side_effect = [user_row(), user_row()]
    conn.fetch.side_effect = [roles_rows("customer"), roles_rows("customer", "manager")]
    user = await admin_users.change_role(conn, ADMIN, TARGET_ID, "manager", "add", "Runs the city fest")

    assert user["roles"] == ["customer", "manager"]
    assert any("INSERT INTO user_roles" in sql for sql in executed_sql(conn))
    args = audit_call(conn)
    assert args[1:4] == (ADMIN["id"], TARGET_ID, "role_added")
    assert json.loads(args[4]) == {"role": "manager"}
    assert args[5] == "Runs the city fest"


@pytest.mark.asyncio
async def test_adding_a_role_the_user_has_is_a_conflict():
    conn = make_conn()
    conn.fetchrow.return_value = user_row()
    conn.fetch.return_value = roles_rows("manager")
    with pytest.raises(HTTPException) as exc:
        await admin_users.change_role(conn, ADMIN, TARGET_ID, "manager", "add", "Again")
    assert exc.value.status_code == 409
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_removing_a_role_the_user_lacks_is_a_conflict():
    conn = make_conn()
    conn.fetchrow.return_value = user_row()
    conn.fetch.return_value = roles_rows("customer")
    with pytest.raises(HTTPException) as exc:
        await admin_users.change_role(conn, ADMIN, TARGET_ID, "manager", "remove", "Not needed")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_the_last_active_admin_keeps_the_admin_role():
    conn = make_conn()
    conn.fetchrow.return_value = user_row()
    conn.fetch.return_value = roles_rows("admin")
    conn.fetchval.return_value = 0
    with pytest.raises(HTTPException) as exc:
        await admin_users.change_role(conn, ADMIN, TARGET_ID, "admin", "remove", "Cleanup")
    assert exc.value.status_code == 409
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_removing_the_only_role_falls_back_to_customer():
    conn = make_conn()
    conn.fetchrow.side_effect = [user_row(), user_row()]
    conn.fetch.side_effect = [roles_rows("manager"), roles_rows("customer")]
    user = await admin_users.change_role(conn, ADMIN, TARGET_ID, "manager", "remove", "Left the organiser")

    sql = executed_sql(conn)
    assert any("DELETE FROM user_roles" in s for s in sql)
    assert any("code = 'customer'" in s for s in sql)
    assert user["roles"] == ["customer"]
    assert audit_call(conn)[3] == "role_removed"


# ── Status ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_cannot_block_themselves():
    conn = make_conn()
    with pytest.raises(HTTPException) as exc:
        await admin_users.change_status(conn, ADMIN, ADMIN["id"], "blocked", "Testing")
    assert exc.value.status_code == 400
    conn.fetchrow.assert_not_called()


@pytest.mark.asyncio
async def test_blocking_updates_status_audits_and_returns_firebase_uid():
    conn = make_conn()
    conn.fetchrow.side_effect = [user_row("active"), user_row("blocked")]
    conn.fetch.return_value = roles_rows("customer")
    user, firebase_uid = await admin_users.change_status(conn, ADMIN, TARGET_ID, "blocked", "Ticket scalping")

    assert user["status"] == "blocked" and "firebase_uid" not in user
    assert firebase_uid == "fb-target"
    update = next(c for c in conn.execute.await_args_list if "UPDATE users SET status" in c.args[0])
    assert update.args[1:] == (TARGET_ID, "blocked")
    args = audit_call(conn)
    assert args[3] == "status_changed"
    assert json.loads(args[4]) == {"from": "active", "to": "blocked"}
    assert args[5] == "Ticket scalping"


@pytest.mark.asyncio
async def test_unblocking_does_not_return_a_firebase_uid():
    conn = make_conn()
    conn.fetchrow.side_effect = [user_row("blocked"), user_row("active")]
    conn.fetch.return_value = roles_rows("customer")
    user, firebase_uid = await admin_users.change_status(conn, ADMIN, TARGET_ID, "active", "Appeal accepted")
    assert user["status"] == "active" and firebase_uid is None


@pytest.mark.asyncio
async def test_setting_the_current_status_is_a_conflict():
    conn = make_conn()
    conn.fetchrow.return_value = user_row("blocked")
    conn.fetch.return_value = roles_rows("customer")
    with pytest.raises(HTTPException) as exc:
        await admin_users.change_status(conn, ADMIN, TARGET_ID, "blocked", "Again")
    assert exc.value.status_code == 409
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_revoke_sessions_never_raises(monkeypatch):
    import firebase_admin_setup

    def boom(uid):
        raise RuntimeError("firebase down")

    monkeypatch.setattr(firebase_admin_setup, "revoke_refresh_tokens", boom)
    await admin_users.revoke_sessions("fb-target")


# ── Manager approvals are audited too ───────────────────────────────────────

@pytest.mark.asyncio
async def test_approving_a_pending_manager_is_audited():
    conn = make_conn()
    req = auth_router_module.ApproveUserRequest(action="approve")
    resp = await auth_router_module.process_approval(TARGET_ID, req, admin=ADMIN, conn=conn)
    assert resp == {"message": "User approved"}
    update = conn.execute.await_args_list[0]
    assert "status='inactive'" in update.args[0] and update.args[1:] == (TARGET_ID, "active")
    assert audit_call(conn)[3] == "manager_approved"


@pytest.mark.asyncio
async def test_approving_a_user_who_is_not_pending_is_404():
    conn = make_conn()
    conn.execute.return_value = "UPDATE 0"
    req = auth_router_module.ApproveUserRequest(action="reject")
    with pytest.raises(HTTPException) as exc:
        await auth_router_module.process_approval(TARGET_ID, req, admin=ADMIN, conn=conn)
    assert exc.value.status_code == 404
