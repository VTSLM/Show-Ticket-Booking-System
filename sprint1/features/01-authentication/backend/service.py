"""
service.py — Pure business-logic for the authentication feature.

All DB interactions happen here; the router only handles HTTP concerns.
"""
from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
from firebase_admin import auth as firebase_auth

from database import get_pool
from schemas import (
    ApprovalAction,
    ApproveUserResponse,
    PendingUser,
    RegisterRequest,
    RegisterResponse,
    RegistrationStatus,
    StakeholderRole,
    UserProfile,
    VerifyTokenResponse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Roles that must go through admin approval before they can log in.
APPROVAL_REQUIRED_ROLES = {StakeholderRole.manager, StakeholderRole.admin}

# Map role → frontend route
ROLE_REDIRECT_MAP: dict[str, str] = {
    "admin": "/admin/dashboard",
    "manager": "/manager/dashboard",
    "customer": "/browse",
}


def _redirect_for_roles(roles: list[str]) -> str:
    """Return the most privileged redirect path for the given roles."""
    for role in ("admin", "manager", "customer"):
        if role in roles:
            return ROLE_REDIRECT_MAP[role]
    return "/browse"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


async def register_user(payload: RegisterRequest) -> RegisterResponse:
    """
    1. Verify Firebase token.
    2. Upsert user row into the DB.
    3. Assign role.
       - customer  → immediately active
       - manager / admin → status = 'inactive' (pending_approval)
    """
    # Verify token
    try:
        decoded = firebase_auth.verify_id_token(payload.firebase_token)
    except Exception as exc:
        raise ValueError(f"Invalid Firebase token: {exc}")

    firebase_uid: str = decoded["uid"]
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check if user already exists by firebase_uid
            existing = await conn.fetchrow(
                "SELECT id, status FROM users WHERE firebase_uid = $1", firebase_uid
            )
            if existing:
                # Return their current state
                roles = await conn.fetch(
                    """
                    SELECT r.code FROM user_roles ur
                    JOIN roles r ON r.id = ur.role_id
                    WHERE ur.user_id = $1
                    """,
                    existing["id"],
                )
                role_codes = [r["code"] for r in roles]
                status = (
                    RegistrationStatus.active
                    if existing["status"] == "active"
                    else RegistrationStatus.pending_approval
                )
                return RegisterResponse(
                    user_id=str(existing["id"]),
                    name=payload.name,
                    email=payload.email,
                    role=payload.requested_role.value,
                    status=status,
                    message="User already registered.",
                )

            # Check if email is already in database (e.g. from seed data or prior registration)
            existing_email = await conn.fetchrow(
                "SELECT id, firebase_uid, status FROM users WHERE email = $1", payload.email
            )
            if existing_email:
                if str(existing_email["firebase_uid"]).startswith("DEV_FIREBASE_UID_"):
                    # Seed fixture user: update with the real Firebase UID
                    await conn.execute(
                        "UPDATE users SET firebase_uid = $1, name = $2, phone = COALESCE($3, phone) WHERE id = $4",
                        firebase_uid,
                        payload.name,
                        payload.phone,
                        existing_email["id"],
                    )
                    user_id = existing_email["id"]
                    needs_approval = False
                else:
                    raise ValueError("An account with this email address already exists. Please log in.")
            else:
                # Determine initial user_status
                needs_approval = payload.requested_role in APPROVAL_REQUIRED_ROLES
                user_db_status = "inactive" if needs_approval else "active"

                try:
                    # Insert user
                    user_id = await conn.fetchval(
                        """
                        INSERT INTO users (firebase_uid, name, email, phone, status)
                        VALUES ($1, $2, $3, $4, $5::user_status)
                        RETURNING id
                        """,
                        firebase_uid,
                        payload.name,
                        payload.email,
                        payload.phone,
                        user_db_status,
                    )
                except asyncpg.UniqueViolationError:
                    raise ValueError("An account with this email address already exists.")

            # Get role id
            role_id = await conn.fetchval(
                "SELECT id FROM roles WHERE code = $1",
                payload.requested_role.value,
            )
            if role_id is None:
                # Role doesn't exist yet — create it on the fly
                role_id = await conn.fetchval(
                    "INSERT INTO roles(code, name) VALUES($1, $2) RETURNING id",
                    payload.requested_role.value,
                    payload.requested_role.value.title(),
                )

            await conn.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2)",
                user_id,
                role_id,
            )

    registration_status = (
        RegistrationStatus.pending_approval
        if needs_approval
        else RegistrationStatus.active
    )
    message = (
        "Registration successful! Your account is pending admin approval."
        if needs_approval
        else "Registration successful! You can now log in."
    )

    return RegisterResponse(
        user_id=str(user_id),
        name=payload.name,
        email=payload.email,
        role=payload.requested_role.value,
        status=registration_status,
        message=message,
    )


# ---------------------------------------------------------------------------
# Token verification / login
# ---------------------------------------------------------------------------


async def verify_and_get_profile(firebase_token: str) -> VerifyTokenResponse:
    """
    Verify a Firebase ID token and return the full user profile.
    Raises ValueError for invalid token, LookupError if user not in DB.
    """
    try:
        decoded = firebase_auth.verify_id_token(firebase_token)
    except Exception as exc:
        raise ValueError(f"Invalid Firebase token: {exc}")

    firebase_uid: str = decoded["uid"]
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.firebase_uid, u.name, u.email, u.phone, u.status,
                   COALESCE(
                       array_agg(r.code) FILTER (WHERE r.code IS NOT NULL), ARRAY[]::text[]
                   ) AS roles
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles r ON r.id = ur.role_id
            WHERE u.firebase_uid = $1
            GROUP BY u.id
            """,
            firebase_uid,
        )

    if row is None:
        raise LookupError("User not found. Please register first.")

    roles: list[str] = list(row["roles"])
    profile = UserProfile(
        user_id=str(row["id"]),
        firebase_uid=row["firebase_uid"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        roles=roles,
        status=row["status"],
        redirect_to=_redirect_for_roles(roles) if row["status"] == "active" else "/pending-approval",
    )
    return VerifyTokenResponse(user=profile)


# ---------------------------------------------------------------------------
# Admin: pending approvals
# ---------------------------------------------------------------------------


async def list_pending_users() -> list[PendingUser]:
    """Return all users whose status is 'inactive' (i.e. awaiting approval)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.id, u.name, u.email, u.created_at,
                   COALESCE(
                       array_agg(r.code) FILTER (WHERE r.code IS NOT NULL), ARRAY[]::text[]
                   ) AS roles
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles r ON r.id = ur.role_id
            WHERE u.status = 'inactive'
            GROUP BY u.id
            ORDER BY u.created_at ASC
            """,
        )

    return [
        PendingUser(
            user_id=str(row["id"]),
            name=row["name"],
            email=row["email"],
            requested_role=", ".join(row["roles"]) if row["roles"] else "unknown",
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]


async def process_approval(
    user_id: str, action: ApprovalAction
) -> ApproveUserResponse:
    """Approve or reject (delete) a pending user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, status FROM users WHERE id = $1::uuid",
            user_id,
        )
        if existing is None:
            raise LookupError(f"User {user_id!r} not found.")

        if action == ApprovalAction.approve:
            await conn.execute(
                "UPDATE users SET status = 'active' WHERE id = $1::uuid",
                user_id,
            )
            msg = "User approved and activated."
        else:
            # Rejection: delete the user record (and cascade roles/bookings)
            await conn.execute(
                "DELETE FROM users WHERE id = $1::uuid",
                user_id,
            )
            # Also revoke the Firebase account so the email can be reused
            try:
                fb_uid = await conn.fetchval(
                    "SELECT firebase_uid FROM users WHERE id = $1::uuid", user_id
                )
                if fb_uid:
                    firebase_auth.delete_user(fb_uid)
            except Exception:
                pass  # Best-effort
            msg = "User rejected and removed."

    return ApproveUserResponse(user_id=user_id, action=action, message=msg)
