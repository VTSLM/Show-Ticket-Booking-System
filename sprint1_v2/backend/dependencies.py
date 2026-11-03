from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
from database import get_conn
from firebase_admin_setup import verify_firebase_token

security = HTTPBearer()

async def get_current_firebase_uid(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    try:
        decoded = verify_firebase_token(credentials.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

async def get_current_user(
    uid: str = Depends(get_current_firebase_uid),
    conn: asyncpg.Connection = Depends(get_conn)
) -> dict:
    row = await conn.fetchrow(
        """
        SELECT u.id, u.firebase_uid, u.name, u.email, u.phone, u.status,
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
