from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import asyncpg
from database import get_conn
from dependencies import get_current_firebase_uid, get_current_user, require_role
from firebase_admin_setup import verify_firebase_token

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    id_token: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str = "customer"  # customer | manager

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

    uid = decoded["uid"]
    role = req.role.lower()
    if role not in ("customer", "manager"):
        raise HTTPException(
            status_code=400,
            detail="Role must be customer or manager. Admin accounts require an invite."
        )

    existing = await conn.fetchrow("SELECT id, status FROM users WHERE firebase_uid=$1", uid)
    if existing:
        raise HTTPException(status_code=409, detail="User already registered")

    # Insert user
    user_status = "active" if role in ("customer", "admin") else "inactive"
    user_id = await conn.fetchval(
        """INSERT INTO users (firebase_uid, name, email, phone, status)
           VALUES ($1, $2, $3, $4, $5) RETURNING id""",
        uid, req.name, req.email, req.phone, user_status
    )

    # Assign role
    role_id = await conn.fetchval("SELECT id FROM roles WHERE code=$1", role)
    if not role_id:
        # Seed roles if not present
        await conn.execute(
            "INSERT INTO roles (code, name) VALUES ('customer','Customer'),('manager','Manager'),('admin','Admin') ON CONFLICT (code) DO NOTHING"
        )
        role_id = await conn.fetchval("SELECT id FROM roles WHERE code=$1", role)

    await conn.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        user_id, role_id
    )

    msg = "Registration successful" if role == "customer" else "Registration submitted. Awaiting admin approval."
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

    uid = decoded["uid"]
    row = await conn.fetchrow(
        """SELECT u.id, u.name, u.email, u.status,
                  array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
           FROM users u
           LEFT JOIN user_roles ur ON ur.user_id=u.id
           LEFT JOIN roles r ON r.id=ur.role_id
           WHERE u.firebase_uid=$1 GROUP BY u.id""",
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
    return {"user": user, "firebase_uid": uid}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user


# Admin routes
admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.get("/pending")
async def list_pending(
    _: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn)
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
    _: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn)
):
    if req.action == "approve":
        await conn.execute("UPDATE users SET status='active' WHERE id=$1", user_id)
        return {"message": "User approved"}
    elif req.action == "reject":
        await conn.execute("UPDATE users SET status='blocked' WHERE id=$1", user_id)
        return {"message": "User rejected"}
    else:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
