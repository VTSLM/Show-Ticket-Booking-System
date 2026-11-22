from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
from database import get_conn
from firebase_admin_setup import EMAIL_NOT_VERIFIED, is_email_verified, verify_firebase_token

security = HTTPBearer()

async def get_current_firebase_uid(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    try:
        decoded = verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    # Unverified email/password accounts can't use the app yet (#208)
    if not is_email_verified(decoded):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=EMAIL_NOT_VERIFIED)
    return decoded["uid"]

async def get_current_user(
    uid: str = Depends(get_current_firebase_uid),
    conn: asyncpg.Connection = Depends(get_conn),
    request: Request = None,
) -> dict:
    row = await conn.fetchrow(
        """
        SELECT u.id, u.firebase_uid, u.name, u.email, u.phone, u.birthdate, u.status,
               u.is_verified, u.publication, u.avatar_url, u.bio,
               array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE u.firebase_uid = $1
        GROUP BY u.id
        """,
        uid
    )
    if not row:
        raise HTTPException(status_code=404, detail="User profile not found. Please register first.")
    user = dict(row)
    user["roles"] = list(user["roles"]) if user["roles"] else []
    # Only active accounts may use the API. Pending managers and blocked users are
    # turned away here, not just on the login screen.
    if user["status"] != "active":
        detail = "Account pending admin approval" if user["status"] == "inactive" else "Account blocked"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    # Server-Side Inactivity & Revocation Enforcement
    if request is not None and hasattr(request, "headers"):
        session_id = request.headers.get("x-session-id")
        if session_id:
            from services.session_service import validate_session, touch_session
            is_valid, reason, session = await validate_session(conn, session_id, str(user["id"]))
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=reason or "Your session expired due to inactivity. Please log in again.",
                )
            user["session_id"] = session_id
            user["session"] = session
            await touch_session(conn, session_id)

    return user

def require_role(*roles: str):
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        for role in roles:
            if role in user_roles:
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {list(roles)}"
        )
    return checker
