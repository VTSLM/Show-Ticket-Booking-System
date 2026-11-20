"""Admin user management endpoints (#138). Logic lives in services/admin_users.py."""
from typing import Literal, Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from database import get_conn
from dependencies import require_role
from services import admin_users

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

ADMIN_ONLY = require_role("admin")


class RoleChange(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    role: Literal["manager", "admin"]
    action: Literal["add", "remove"]
    reason: str = Field(..., min_length=3, max_length=500)


class StatusChange(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal["active", "blocked"]
    reason: str = Field(..., min_length=3, max_length=500)


@router.get("")
async def list_users(
    q: Optional[str] = Query(None, max_length=100, description="Search name or email"),
    role: Optional[Literal["customer", "manager", "admin"]] = None,
    status: Optional[Literal["active", "inactive", "blocked"]] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: dict = Depends(ADMIN_ONLY),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await admin_users.list_users(conn, q, role, status, page, page_size)


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    _: dict = Depends(ADMIN_ONLY),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await admin_users.get_user(conn, user_id)


@router.patch("/{user_id}/roles")
async def change_role(
    user_id: str,
    body: RoleChange,
    admin: dict = Depends(ADMIN_ONLY),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await admin_users.change_role(conn, admin, user_id, body.role, body.action, body.reason)


@router.patch("/{user_id}/status")
async def change_status(
    user_id: str,
    body: StatusChange,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(ADMIN_ONLY),
    conn: asyncpg.Connection = Depends(get_conn),
):
    user, firebase_uid = await admin_users.change_status(conn, admin, user_id, body.status, body.reason)
    if firebase_uid:
        background_tasks.add_task(admin_users.revoke_sessions, firebase_uid)
    return user
