"""
dependencies.py — FastAPI dependency functions (token verification, role guards).
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from firebase_admin import auth as firebase_auth

from database import get_pool


# ---------------------------------------------------------------------------
# Firebase token → verified UID
# ---------------------------------------------------------------------------


async def get_current_firebase_uid(request: Request) -> str:
    """Extract and verify the Firebase ID token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
        )
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {exc}",
        )


# ---------------------------------------------------------------------------
# DB-backed current user
# ---------------------------------------------------------------------------


async def get_current_user(
    firebase_uid: str = Depends(get_current_firebase_uid),
) -> dict:
    """Load the current user row + roles from the database."""
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
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
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in database. Please register first.",
        )
    return dict(user)


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------


def require_role(*allowed_roles: str):
    """Return a dependency that asserts the current user has one of the given roles."""

    async def _guard(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles: list[str] = current_user.get("roles") or []
        if not any(r in user_roles for r in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(allowed_roles)}.",
            )
        if current_user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not yet active. Please await admin approval.",
            )
        return current_user

    return _guard
