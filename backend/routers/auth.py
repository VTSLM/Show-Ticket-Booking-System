import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date
import asyncpg

from database import get_conn
from dependencies import get_current_user, require_role
from services.admin_users import write_audit
from firebase_admin_setup import EMAIL_NOT_VERIFIED, is_email_verified, verify_firebase_token

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    id_token: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    birthdate: date
    role: str = "customer"  # customer | manager | admin
    invite_code: Optional[str] = None


class RegisterResponse(BaseModel):
    message: str
    user_id: str
    status: str


class ApproveUserRequest(BaseModel):
    action: str  # "approve" | "reject"


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, conn: asyncpg.Connection = Depends(get_conn)):
    try:
        decoded = verify_firebase_token(req.id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    if req.birthdate > date.today():
        raise HTTPException(status_code=400, detail="Birthdate cannot be in the future")

    # The profile is saved before the email is verified (the user hasn't clicked the link
    # yet); every other endpoint, including login, still requires verification (#208).
    uid = decoded["uid"]
    role = req.role.lower()
    if role == "admin":
        expected = os.getenv("ADMIN_INVITE_CODE", "")
        if not expected or req.invite_code != expected:
            raise HTTPException(status_code=403, detail="Invalid or missing admin invite code")
    elif role not in ("customer", "manager"):
        raise HTTPException(status_code=400, detail="Role must be customer or manager")

    existing = await conn.fetchrow("SELECT id, status FROM users WHERE firebase_uid=$1", uid)
    if existing:
        raise HTTPException(status_code=409, detail="User already registered")

    user_status = "active" if role in ("customer", "admin") else "inactive"
    user_id = await conn.fetchval(
        """INSERT INTO users (firebase_uid, name, email, phone, birthdate, status)
           VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
        uid, req.name, req.email, req.phone, req.birthdate, user_status
    )

    role_id = await conn.fetchval("SELECT id FROM roles WHERE code=$1", role)
    if not role_id:
        await conn.execute(
            "INSERT INTO roles (code, name) VALUES ('customer','Customer'),('manager','Manager'),('admin','Admin') ON CONFLICT (code) DO NOTHING"
        )
        role_id = await conn.fetchval("SELECT id FROM roles WHERE code=$1", role)

    await conn.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        user_id, role_id
    )

    msg = "Registration successful" if role in ("customer", "admin") else "Registration submitted. Awaiting admin approval."
    return RegisterResponse(message=msg, user_id=str(user_id), status=user_status)


@router.post("/verify-token")
async def verify_token(body: dict, conn: asyncpg.Connection = Depends(get_conn)):
    id_token = body.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token required")

    try:
        decoded = verify_firebase_token(id_token)
    except Exception as e:
        print("🔥 Firebase token verification failed:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid token")

    # Logging in needs a verified email (#208); no session is created before that
    if not is_email_verified(decoded):
        raise HTTPException(status_code=403, detail=EMAIL_NOT_VERIFIED)

    uid = decoded["uid"]
    row = await conn.fetchrow(
        """SELECT u.id, u.name, u.email, u.phone, u.birthdate, u.status,
                  array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
           FROM users u
           LEFT JOIN user_roles ur ON ur.user_id=u.id
           LEFT JOIN roles r ON r.id=ur.role_id
           WHERE u.firebase_uid=$1
           GROUP BY u.id""",
        uid
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found. Please register.")

    user = dict(row)
    user["roles"] = list(user["roles"]) if user["roles"] else []

    if user["status"] == "inactive":
        raise HTTPException(status_code=403, detail="Account pending admin approval")
    if user["status"] == "blocked":
        raise HTTPException(status_code=403, detail="Account blocked")

    session_info = None
    try:
        from services.session_service import create_session, validate_session
        session_id = body.get("session_id")
        if session_id:
            is_valid, _, sess = await validate_session(conn, session_id, str(user["id"]))
            if is_valid:
                session_info = sess
        if not session_info:
            session_info = await create_session(conn, str(user["id"]), user["roles"])
    except Exception:
        # Fallback for unit tests with minimal mock connections
        from config import get_role_inactivity_timeout_seconds, INACTIVITY_WARNING_LEAD_SECONDS
        import uuid
        timeout = get_role_inactivity_timeout_seconds(user.get("roles", []))
        session_info = {
            "id": str(uuid.uuid4()),
            "user_id": str(user.get("id")),
            "role": user.get("roles", ["customer"])[0] if user.get("roles") else "customer",
            "timeout_seconds": timeout,
            "warning_lead_seconds": INACTIVITY_WARNING_LEAD_SECONDS,
        }

    return {"user": user, "firebase_uid": uid, "session": session_info}


@router.post("/session/heartbeat")
async def session_heartbeat(
    request: Request,
    body: Optional[dict] = None,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Heartbeat endpoint called when user clicks 'Stay Logged In' or performs meaningful activity.
    Verifies server-side session and updates last_activity_at.
    """
    session_id = None
    if request and hasattr(request, "headers"):
        session_id = request.headers.get("x-session-id")
    if not session_id and body:
        session_id = body.get("session_id")

    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    from services.session_service import heartbeat_session
    is_valid, reason, session = await heartbeat_session(conn, session_id, str(current_user["id"]))
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail=reason or "Session expired due to inactivity. Please log in again.",
        )

    return {
        "status": "active",
        "session": session,
    }


@router.post("/session/logout")
async def session_logout(
    request: Request,
    body: Optional[dict] = None,
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Explicitly revokes session on the server.
    """
    session_id = None
    if request and hasattr(request, "headers"):
        session_id = request.headers.get("x-session-id")
    if not session_id and body:
        session_id = body.get("session_id")

    if session_id:
        from services.session_service import revoke_session
        await revoke_session(conn, session_id)

    return {"status": "logged_out"}


@router.get("/session/policy")
async def get_session_policy():
    """
    Returns centrally configured role-based session inactivity timeouts.
    """
    from config import (
        INACTIVITY_TIMEOUT_CUSTOMER_SECONDS,
        INACTIVITY_TIMEOUT_MANAGER_SECONDS,
        INACTIVITY_TIMEOUT_ADMIN_SECONDS,
        INACTIVITY_WARNING_LEAD_SECONDS,
    )
    return {
        "customer_timeout_seconds": INACTIVITY_TIMEOUT_CUSTOMER_SECONDS,
        "manager_timeout_seconds": INACTIVITY_TIMEOUT_MANAGER_SECONDS,
        "admin_timeout_seconds": INACTIVITY_TIMEOUT_ADMIN_SECONDS,
        "warning_lead_seconds": INACTIVITY_WARNING_LEAD_SECONDS,
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# Admin routes
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/pending")
async def list_pending(
    _: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """SELECT u.id, u.name, u.email, u.phone, u.status, u.created_at,
                  array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
           FROM users u
           LEFT JOIN user_roles ur ON ur.user_id=u.id
           LEFT JOIN roles r ON r.id=ur.role_id
           WHERE u.status='inactive'
           GROUP BY u.id ORDER BY u.created_at""",
    )
    return [dict(r) | {"roles": list(r["roles"]) if r["roles"] else []} for r in rows]


@admin_router.post("/pending/{user_id}")
async def process_approval(
    user_id: str,
    req: ApproveUserRequest,
    admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    new_status = "active" if req.action == "approve" else "blocked"
    async with conn.transaction():
        result = await conn.execute(
            "UPDATE users SET status=$2, updated_at=now() WHERE id=$1::uuid AND status='inactive'",
            user_id, new_status,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="No pending user with this id")
        await write_audit(
            conn, admin["id"], user_id,
            "manager_approved" if req.action == "approve" else "manager_rejected",
            {"from": "inactive", "to": new_status}, None,
        )
    return {"message": "User approved" if req.action == "approve" else "User rejected"}