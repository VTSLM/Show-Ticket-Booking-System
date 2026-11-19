"""
Role-based session management and server-side inactivity timeout enforcement.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
import uuid
import asyncpg

from config import (
    INACTIVITY_WARNING_LEAD_SECONDS,
    get_role_inactivity_timeout_seconds,
)


def _is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


async def create_session(
    conn: asyncpg.Connection,
    user_id: str,
    roles: list[str],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new server-verifiable session pinned to the user's role and inactivity timeout.
    """
    timeout_seconds = get_role_inactivity_timeout_seconds(roles)
    primary_role = "customer"
    normalized_roles = [r.lower() for r in roles]
    if "admin" in normalized_roles:
        primary_role = "admin"
    elif "manager" in normalized_roles or "organizer" in normalized_roles:
        primary_role = "manager"

    row = await conn.fetchrow(
        """
        INSERT INTO user_sessions (
            user_id, role, timeout_seconds, last_activity_at, created_at,
            ip_address, user_agent
        )
        VALUES ($1::uuid, $2, $3, now(), now(), $4, $5)
        RETURNING id, user_id, role, timeout_seconds, last_activity_at, created_at
        """,
        user_id,
        primary_role,
        timeout_seconds,
        ip_address,
        user_agent,
    )

    session_data = dict(row)
    session_data["id"] = str(session_data["id"])
    session_data["user_id"] = str(session_data["user_id"])
    session_data["warning_lead_seconds"] = INACTIVITY_WARNING_LEAD_SECONDS
    return session_data


async def validate_session(
    conn: asyncpg.Connection,
    session_id: str,
    user_id: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Validates server-side session:
    1. Checks session exists.
    2. Matches authenticated user.
    3. Confirms session is not revoked.
    4. Enforces inactivity timeout against server timestamp (never trusting client timestamp).
    """
    if not session_id or not _is_valid_uuid(session_id):
        return False, "Invalid session identifier", None

    row = await conn.fetchrow(
        """
        SELECT id, user_id, role, timeout_seconds, last_activity_at, created_at, revoked_at
        FROM user_sessions
        WHERE id = $1::uuid
        """,
        session_id,
    )
    if not row:
        return False, "Session not found", None

    session = dict(row)
    session["id"] = str(session["id"])
    session["user_id"] = str(session["user_id"])

    if session["user_id"] != str(user_id):
        return False, "Session does not match authenticated user", None

    if session["revoked_at"] is not None:
        return False, "Session has been logged out or revoked", None

    now = datetime.now(timezone.utc)
    last_act = session["last_activity_at"]
    if last_act.tzinfo is None:
        last_act = last_act.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - last_act).total_seconds()
    timeout_seconds = int(session["timeout_seconds"])

    if elapsed_seconds > timeout_seconds:
        # Mark revoked on server
        await conn.execute(
            "UPDATE user_sessions SET revoked_at = now() WHERE id = $1::uuid",
            session_id,
        )
        return False, "Your session expired due to inactivity. Please log in again.", session

    return True, "", session


async def touch_session(
    conn: asyncpg.Connection,
    session_id: str,
    min_interval_seconds: int = 15,
) -> bool:
    """
    Updates last_activity_at on meaningful user requests.
    Throttled by min_interval_seconds to avoid excessive DB writes.
    """
    if not session_id or not _is_valid_uuid(session_id):
        return False

    res = await conn.execute(
        """
        UPDATE user_sessions
        SET last_activity_at = now()
        WHERE id = $1::uuid
          AND revoked_at IS NULL
          AND EXTRACT(EPOCH FROM (now() - last_activity_at)) >= $2
        """,
        session_id,
        min_interval_seconds,
    )
    return res != "UPDATE 0"


async def heartbeat_session(
    conn: asyncpg.Connection,
    session_id: str,
    user_id: str,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Refreshes session last_activity_at upon explicit user action ("Stay Logged In").
    """
    is_valid, reason, session = await validate_session(conn, session_id, user_id)
    if not is_valid:
        return False, reason, None

    await conn.execute(
        "UPDATE user_sessions SET last_activity_at = now() WHERE id = $1::uuid",
        session_id,
    )

    remaining_seconds = session["timeout_seconds"]
    session["remaining_seconds"] = remaining_seconds
    session["warning_lead_seconds"] = INACTIVITY_WARNING_LEAD_SECONDS
    return True, "Session refreshed", session


async def revoke_session(
    conn: asyncpg.Connection,
    session_id: str,
    user_id: Optional[str] = None,
) -> bool:
    """
    Revokes a specific session on explicit logout or inactivity expiry.
    """
    if not session_id or not _is_valid_uuid(session_id):
        return False

    if user_id:
        res = await conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = now()
            WHERE id = $1::uuid AND user_id = $2::uuid AND revoked_at IS NULL
            """,
            session_id,
            user_id,
        )
    else:
        res = await conn.execute(
            """
            UPDATE user_sessions
            SET revoked_at = now()
            WHERE id = $1::uuid AND revoked_at IS NULL
            """,
            session_id,
        )
    return res != "UPDATE 0"


async def revoke_all_user_sessions(
    conn: asyncpg.Connection,
    user_id: str,
) -> int:
    """
    Revokes all active sessions for a user (e.g. account blocked or password change).
    """
    res = await conn.execute(
        """
        UPDATE user_sessions
        SET revoked_at = now()
        WHERE user_id = $1::uuid AND revoked_at IS NULL
        """,
        user_id,
    )
    # Parse "UPDATE N"
    try:
        return int(res.split()[-1])
    except Exception:
        return 0
