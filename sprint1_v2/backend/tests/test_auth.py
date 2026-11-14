"""Unit tests for routers.auth.verify_token.

These tests isolate the authentication endpoint from Firebase and PostgreSQL:
- Firebase token verification is mocked.
- The database connection is a small fake object.

Place this file at: backend/tests/test_auth.py
Run from the backend directory with: pytest -q tests/test_auth.py
"""

import asyncio

import pytest
from fastapi import HTTPException

from routers import auth


class FakeConn:
    """Minimal asyncpg-like connection used by the endpoint under test."""

    def __init__(self, row=None):
        self.row = row
        self.queries = []

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        return self.row


async def call_verify_token(body, conn, decoded=None, firebase_error=None):
    """Call the real endpoint function with its dependencies replaced."""
    if firebase_error is not None:
        def fake_verify(_token):
            raise firebase_error
    else:
        def fake_verify(_token):
            return decoded

    original = auth.verify_firebase_token
    auth.verify_firebase_token = fake_verify
    try:
        return await auth.verify_token(body, conn)
    finally:
        auth.verify_firebase_token = original


def run(coro):
    return asyncio.run(coro)


def test_verify_token_valid_active_customer():
    conn = FakeConn({
        "id": "user-1",
        "name": "Test Customer",
        "email": "customer@example.com",
        "birthdate": None,
        "status": "active",
        "roles": ["customer"],
    })

    result = run(call_verify_token(
        {"id_token": "valid-token"},
        conn,
        decoded={"uid": "firebase-customer-1"},
    ))

    assert result["firebase_uid"] == "firebase-customer-1"
    assert result["user"]["status"] == "active"
    assert result["user"]["roles"] == ["customer"]


def test_verify_token_missing_id_token():
    conn = FakeConn()

    with pytest.raises(HTTPException) as exc:
        run(call_verify_token({}, conn, decoded={"uid": "unused"}))

    assert exc.value.status_code == 400
    assert exc.value.detail == "id_token required"


def test_verify_token_invalid_firebase_token():
    conn = FakeConn()

    with pytest.raises(HTTPException) as exc:
        run(call_verify_token(
            {"id_token": "bad-token"},
            conn,
            firebase_error=Exception("Firebase rejected token"),
        ))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


def test_verify_token_firebase_user_not_registered():
    conn = FakeConn(row=None)

    with pytest.raises(HTTPException) as exc:
        run(call_verify_token(
            {"id_token": "valid-token"},
            conn,
            decoded={"uid": "firebase-unknown"},
        ))

    assert exc.value.status_code == 404
    assert exc.value.detail == "User not found. Please register."


def test_verify_token_inactive_manager_is_rejected():
    conn = FakeConn({
        "id": "manager-1",
        "name": "Pending Manager",
        "email": "manager@example.com",
        "birthdate": None,
        "status": "inactive",
        "roles": ["manager"],
    })

    with pytest.raises(HTTPException) as exc:
        run(call_verify_token(
            {"id_token": "manager-token"},
            conn,
            decoded={"uid": "firebase-manager-1"},
        ))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Account pending admin approval"


def test_verify_token_blocked_user_is_rejected():
    conn = FakeConn({
        "id": "blocked-1",
        "name": "Blocked User",
        "email": "blocked@example.com",
        "birthdate": None,
        "status": "blocked",
        "roles": ["customer"],
    })

    with pytest.raises(HTTPException) as exc:
        run(call_verify_token(
            {"id_token": "blocked-token"},
            conn,
            decoded={"uid": "firebase-blocked-1"},
        ))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Account blocked"


def test_verify_token_active_manager_is_allowed():
    conn = FakeConn({
        "id": "manager-2",
        "name": "Approved Manager",
        "email": "approved-manager@example.com",
        "birthdate": None,
        "status": "active",
        "roles": ["manager"],
    })

    result = run(call_verify_token(
        {"id_token": "approved-manager-token"},
        conn,
        decoded={"uid": "firebase-manager-2"},
    ))

    assert result["user"]["status"] == "active"
    assert result["user"]["roles"] == ["manager"]


def test_verify_token_active_admin_is_allowed():
    conn = FakeConn({
        "id": "admin-1",
        "name": "Test Admin",
        "email": "admin@example.com",
        "birthdate": None,
        "status": "active",
        "roles": ["admin"],
    })

    result = run(call_verify_token(
        {"id_token": "admin-token"},
        conn,
        decoded={"uid": "firebase-admin-1"},
    ))

    assert result["user"]["roles"] == ["admin"]
    assert result["user"]["status"] == "active"
