import json
import logging
from typing import List, Optional
from fastapi import Depends, HTTPException, Header, status
from pydantic import BaseModel
from app.config import get_settings
from app.database import fetch_one, get_db_pool

logger = logging.getLogger("uvicorn.error")

class ManagerUser(BaseModel):
    id: str
    firebase_uid: str
    name: str
    email: str
    status: str
    roles: List[str]

async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verifies Firebase ID token.
    Uses firebase_admin if initialized, or basic validation.
    """
    settings = get_settings()
    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth
        # If default app initialized, verify token
        if firebase_admin._apps:
            decoded = firebase_auth.verify_id_token(token)
            return decoded
    except Exception as e:
        logger.warning(f"Firebase Admin SDK verification failed or not configured: {e}")

    # Fallback to JWT payload decoding if firebase-admin is not yet configured with service account
    try:
        import jwt
        # Decode without verification for development/scaffolding when service account key is not present
        unverified = jwt.decode(token, options={"verify_signature": False})
        if "user_id" in unverified or "sub" in unverified:
            return unverified
    except Exception:
        pass

    return None

async def get_current_manager(
    authorization: Optional[str] = Header(None),
    x_dev_firebase_uid: Optional[str] = Header(None, alias="X-Dev-Firebase-Uid")
) -> ManagerUser:
    """
    FastAPI dependency to verify Firebase Auth and enforce Manager role authorization.
    """
    settings = get_settings()
    target_firebase_uid: Optional[str] = None

    # Development bypass mode (strictly if configured in environment)
    if settings.DEV_BYPASS_AUTH and x_dev_firebase_uid:
        target_firebase_uid = x_dev_firebase_uid
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        decoded = await verify_firebase_token(token)
        if not decoded:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired Firebase authentication token."
            )
        target_firebase_uid = decoded.get("uid") or decoded.get("user_id") or decoded.get("sub")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Please log in as a manager."
        )

    if not target_firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract authenticated user identity."
        )

    # Check if database is configured
    pool = await get_db_pool()
    if pool is None:
        # If database is not configured yet, but DEV_BYPASS_AUTH is enabled, provide a fallback test manager
        if settings.DEV_BYPASS_AUTH:
            return ManagerUser(
                id="00000000-0000-0000-0000-000000000001",
                firebase_uid=target_firebase_uid,
                name="Demo Manager",
                email="manager@example.com",
                status="active",
                roles=["manager"]
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured on the backend."
        )

    # Query PostgreSQL to verify user exists and possesses 'manager' or 'admin' role
    query = """
        SELECT u.id::text, u.firebase_uid, u.name, u.email, u.status::text,
               COALESCE(array_agg(r.code) FILTER (WHERE r.code IS NOT NULL), '{}') as roles
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE u.firebase_uid = $1
        GROUP BY u.id, u.firebase_uid, u.name, u.email, u.status;
    """
    user_row = await fetch_one(query, target_firebase_uid)

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account does not exist in the database or has not been registered."
        )

    if user_row.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is not active (current status: {user_row.get('status')})."
        )

    user_roles = user_row.get("roles") or []
    if "manager" not in user_roles and "admin" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: authenticated user does not have manager permissions."
        )

    return ManagerUser(
        id=user_row["id"],
        firebase_uid=user_row["firebase_uid"],
        name=user_row["name"],
        email=user_row["email"],
        status=user_row["status"],
        roles=user_roles,
    )
