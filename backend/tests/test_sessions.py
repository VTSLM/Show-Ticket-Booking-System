"""
Unit tests for Role-Based Inactivity Timeout and Automatic Logout.
Tests cover:
1. Role-based timeout limits: Customer (30m), Manager (20m), Admin (15m).
2. Server-side session creation and verification.
3. Inactivity expiry enforcement (server timestamp, not trusting client).
4. Rejection of expired sessions even with valid Firebase ID tokens.
5. Session revocation on manual logout and inactivity.
6. Heartbeat / keep-alive functionality.
7. Multi-role precedence (highest privilege role determines timeout).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from fastapi import HTTPException, Request

from config import (
    INACTIVITY_TIMEOUT_ADMIN_SECONDS,
    INACTIVITY_TIMEOUT_CUSTOMER_SECONDS,
    INACTIVITY_TIMEOUT_MANAGER_SECONDS,
    INACTIVITY_WARNING_LEAD_SECONDS,
    get_role_inactivity_timeout_seconds,
)
import dependencies
from services import session_service


# ── 1. Role Timeout Policy Tests ──────────────────────────────────────────────

def test_role_timeout_values():
    assert INACTIVITY_TIMEOUT_CUSTOMER_SECONDS == 30 * 60  # 1800s (30m)
    assert INACTIVITY_TIMEOUT_MANAGER_SECONDS == 20 * 60   # 1200s (20m)
    assert INACTIVITY_TIMEOUT_ADMIN_SECONDS == 15 * 60     # 900s (15m)
    assert INACTIVITY_WARNING_LEAD_SECONDS == 2 * 60       # 120s (2m warning)


def test_role_timeout_mapping():
    assert get_role_inactivity_timeout_seconds(["customer"]) == 1800
    assert get_role_inactivity_timeout_seconds(["manager"]) == 1200
    assert get_role_inactivity_timeout_seconds(["organizer"]) == 1200
    assert get_role_inactivity_timeout_seconds(["admin"]) == 900
    # Highest privilege role wins
    assert get_role_inactivity_timeout_seconds(["customer", "manager"]) == 1200
    assert get_role_inactivity_timeout_seconds(["manager", "admin"]) == 900
    assert get_role_inactivity_timeout_seconds([]) == 1800


# ── 2. Session Service Creation & Validation ──────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_customer():
    user_id = str(uuid.uuid4())
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "role": "customer",
        "timeout_seconds": 1800,
        "last_activity_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    session = await session_service.create_session(conn, user_id, ["customer"])

    assert session["timeout_seconds"] == 1800
    assert session["role"] == "customer"
    assert session["warning_lead_seconds"] == 120


@pytest.mark.asyncio
async def test_create_session_manager():
    user_id = str(uuid.uuid4())
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "role": "manager",
        "timeout_seconds": 1200,
        "last_activity_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    session = await session_service.create_session(conn, user_id, ["manager"])
    assert session["timeout_seconds"] == 1200
    assert session["role"] == "manager"


@pytest.mark.asyncio
async def test_create_session_admin():
    user_id = str(uuid.uuid4())
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": uuid.uuid4(),
        "user_id": user_id,
        "role": "admin",
        "timeout_seconds": 900,
        "last_activity_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    session = await session_service.create_session(conn, user_id, ["admin"])
    assert session["timeout_seconds"] == 900
    assert session["role"] == "admin"


@pytest.mark.asyncio
async def test_validate_session_active():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    recent_activity = datetime.now(timezone.utc) - timedelta(minutes=5)

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": session_id,
        "user_id": user_id,
        "role": "customer",
        "timeout_seconds": 1800,
        "last_activity_at": recent_activity,
        "created_at": recent_activity,
        "revoked_at": None,
    }

    is_valid, reason, session = await session_service.validate_session(conn, session_id, user_id)
    assert is_valid is True
    assert reason == ""
    assert session is not None


@pytest.mark.asyncio
async def test_validate_session_expired_by_inactivity():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    # 35 minutes ago, exceeds 30m limit
    stale_activity = datetime.now(timezone.utc) - timedelta(minutes=35)

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": session_id,
        "user_id": user_id,
        "role": "customer",
        "timeout_seconds": 1800,
        "last_activity_at": stale_activity,
        "created_at": stale_activity,
        "revoked_at": None,
    }

    is_valid, reason, session = await session_service.validate_session(conn, session_id, user_id)
    assert is_valid is False
    assert "expired due to inactivity" in reason
    # Confirms session was marked revoked in the database
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_session_revoked():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": session_id,
        "user_id": user_id,
        "role": "admin",
        "timeout_seconds": 900,
        "last_activity_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "revoked_at": datetime.now(timezone.utc),
    }

    is_valid, reason, session = await session_service.validate_session(conn, session_id, user_id)
    assert is_valid is False
    assert "revoked" in reason.lower() or "logged out" in reason.lower()


@pytest.mark.asyncio
async def test_validate_session_user_mismatch():
    user_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": session_id,
        "user_id": other_user_id,
        "role": "customer",
        "timeout_seconds": 1800,
        "last_activity_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "revoked_at": None,
    }

    is_valid, reason, session = await session_service.validate_session(conn, session_id, user_id)
    assert is_valid is False
    assert "does not match" in reason.lower()


# ── 3. Heartbeat & Session Extension Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_heartbeat_active_session():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    recent_activity = datetime.now(timezone.utc) - timedelta(minutes=10)

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": session_id,
        "user_id": user_id,
        "role": "manager",
        "timeout_seconds": 1200,
        "last_activity_at": recent_activity,
        "created_at": recent_activity,
        "revoked_at": None,
    }

    is_valid, reason, session = await session_service.heartbeat_session(conn, session_id, user_id)
    assert is_valid is True
    assert reason == "Session refreshed"
    # Verify last_activity_at was updated
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_heartbeat_expired_session_fails():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    # 25 minutes ago for manager (limit is 20m)
    expired_activity = datetime.now(timezone.utc) - timedelta(minutes=25)

    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": session_id,
        "user_id": user_id,
        "role": "manager",
        "timeout_seconds": 1200,
        "last_activity_at": expired_activity,
        "created_at": expired_activity,
        "revoked_at": None,
    }

    is_valid, reason, session = await session_service.heartbeat_session(conn, session_id, user_id)
    assert is_valid is False
    assert "expired due to inactivity" in reason


# ── 4. End-to-End Dependency Enforcement in get_current_user ──────────────────

@pytest.mark.asyncio
async def test_get_current_user_with_valid_session():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    conn = AsyncMock()
    # 1. Fetch user row
    conn.fetchrow.side_effect = [
        {
            "id": user_id,
            "firebase_uid": "fb-uid-123",
            "name": "Alice Customer",
            "email": "alice@example.com",
            "phone": None,
            "birthdate": None,
            "status": "active",
            "is_verified": True,
            "publication": None,
            "avatar_url": None,
            "bio": None,
            "roles": ["customer"],
        },
        # 2. Fetch session row for validate_session
        {
            "id": session_id,
            "user_id": user_id,
            "role": "customer",
            "timeout_seconds": 1800,
            "last_activity_at": datetime.now(timezone.utc) - timedelta(minutes=2),
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=10),
            "revoked_at": None,
        },
    ]

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"x-session-id": session_id}

    user = await dependencies.get_current_user(
        uid="fb-uid-123",
        conn=conn,
        request=mock_request,
    )

    assert user["id"] == user_id
    assert user["session_id"] == session_id
    assert user["status"] == "active"


@pytest.mark.asyncio
async def test_get_current_user_rejects_expired_session_even_with_valid_token():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        # User profile is valid and active
        {
            "id": user_id,
            "firebase_uid": "fb-uid-123",
            "name": "Bob Admin",
            "email": "bob@ticketflow.com",
            "phone": None,
            "birthdate": None,
            "status": "active",
            "is_verified": True,
            "publication": None,
            "avatar_url": None,
            "bio": None,
            "roles": ["admin"],
        },
        # Session expired (admin limit is 15m; activity 18m ago)
        {
            "id": session_id,
            "user_id": user_id,
            "role": "admin",
            "timeout_seconds": 900,
            "last_activity_at": datetime.now(timezone.utc) - timedelta(minutes=18),
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=30),
            "revoked_at": None,
        },
    ]

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"x-session-id": session_id}

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(
            uid="fb-uid-123",
            conn=conn,
            request=mock_request,
        )

    assert exc.value.status_code == 401
    assert "expired due to inactivity" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_rejects_revoked_session():
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": user_id,
            "firebase_uid": "fb-uid-123",
            "name": "Carol Manager",
            "email": "carol@example.com",
            "phone": None,
            "birthdate": None,
            "status": "active",
            "is_verified": True,
            "publication": None,
            "avatar_url": None,
            "bio": None,
            "roles": ["manager"],
        },
        # Session already revoked
        {
            "id": session_id,
            "user_id": user_id,
            "role": "manager",
            "timeout_seconds": 1200,
            "last_activity_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            "revoked_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
    ]

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"x-session-id": session_id}

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(
            uid="fb-uid-123",
            conn=conn,
            request=mock_request,
        )

    assert exc.value.status_code == 401
    assert "revoked" in exc.value.detail.lower() or "logged out" in exc.value.detail.lower()
