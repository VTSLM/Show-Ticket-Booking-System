"""
Customer Care — customer side (Sprint 2).

Customers can raise support requests about a booking/payment problem,
see their own requests, chat with the support team and reopen a request.

The admin side (see all requests, reply as admin, change status) lives in
routers/support_admin.py.

Tables: support_requests, support_messages (database/003_customer_care.sql)
"""
import uuid as uuid_module
from datetime import datetime
from typing import Literal, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from database import get_conn
from config import GMAIL_USER
from services.support_email_service import send_new_ticket_notification
from dependencies import get_current_user

router = APIRouter(prefix="/api/support", tags=["support"])

Category = Literal["payment", "booking", "refund", "account", "other"]

# Categories that are about money get looked at first.
HIGH_PRIORITY_CATEGORIES = {"payment", "refund"}

# Categories where the customer must say which booking they mean.
BOOKING_REQUIRED_CATEGORIES = {"booking", "refund"}


# ───────────────────────── Request bodies ─────────────────────────

class CreateSupportRequest(BaseModel):
    category: Category
    subject: str = Field(min_length=5, max_length=150)
    message: str = Field(min_length=10, max_length=2000)
    booking_id: Optional[str] = None

    @field_validator("subject", "message")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("cannot be empty")
        return v

    @field_validator("booking_id")
    @classmethod
    def valid_uuid(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        try:
            uuid_module.UUID(v)
        except ValueError:
            raise ValueError("booking_id is not a valid id")
        return v


class AddMessage(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("cannot be empty")
        return v


# ───────────────────────── Helpers ─────────────────────────

def _new_request_number() -> str:
    return f"SR-{datetime.now().strftime('%Y%m%d')}-{uuid_module.uuid4().hex[:6].upper()}"


def _parse_uuid(value: str) -> str:
    try:
        return str(uuid_module.UUID(value))
    except ValueError:
        raise HTTPException(status_code=404, detail="Support request not found")


async def _get_own_request(conn: asyncpg.Connection, request_id: str, user_id: str) -> dict:
    """Fetch a request only if it belongs to this user (customers never see others' requests)."""
    row = await conn.fetchrow(
        """SELECT sr.*, b.booking_number
           FROM support_requests sr
           LEFT JOIN bookings b ON b.id = sr.booking_id
           WHERE sr.id = $1 AND sr.user_id = $2""",
        _parse_uuid(request_id), user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Support request not found")
    return dict(row)


# ───────────────────────── Endpoints ─────────────────────────

@router.post("/requests", status_code=201)
async def create_request(
    req: CreateSupportRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    user_id = str(current_user["id"])

    if req.category in BOOKING_REQUIRED_CATEGORIES and not req.booking_id:
        raise HTTPException(status_code=400, detail="Please select the booking this is about")

    if req.booking_id:
        owns = await conn.fetchval(
            "SELECT 1 FROM bookings WHERE id = $1 AND user_id = $2",
            req.booking_id, user_id,
        )
        if not owns:
            raise HTTPException(status_code=404, detail="Booking not found")

    priority = "high" if req.category in HIGH_PRIORITY_CATEGORIES else "normal"
    request_number = _new_request_number()

    async with conn.transaction():
        row = await conn.fetchrow(
            """INSERT INTO support_requests
                   (request_number, user_id, booking_id, category, subject, priority)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING id, request_number, status, priority, created_at""",
            request_number, user_id, req.booking_id, req.category, req.subject, priority,
        )
        await conn.execute(
            """INSERT INTO support_messages (request_id, sender_id, is_admin, message)
               VALUES ($1, $2, false, $3)""",
            row["id"], user_id, req.message,
        )

    # Email admin on new ticket (item 7 — fire-and-forget)
    try:
        await send_new_ticket_notification(
            admin_email=GMAIL_USER,
            user_name=current_user["name"],
            user_email=current_user["email"],
            subject=req.subject,
            request_number=request_number,
            category=req.category,
            message_preview=req.message,
        )
    except Exception as exc:
        print(f"[support] admin email failed: {exc}")

    return dict(row)


@router.get("/requests")
async def list_my_requests(
    status: Optional[Literal["open", "in_progress", "resolved", "closed"]] = None,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """SELECT sr.id, sr.request_number, sr.category, sr.subject, sr.status,
                  sr.priority, sr.created_at, sr.updated_at, b.booking_number,
                  (SELECT COUNT(*) FROM support_messages m WHERE m.request_id = sr.id) AS message_count,
                  (SELECT m.is_admin FROM support_messages m WHERE m.request_id = sr.id
                    ORDER BY m.created_at DESC LIMIT 1) AS last_reply_by_admin
           FROM support_requests sr
           LEFT JOIN bookings b ON b.id = sr.booking_id
           WHERE sr.user_id = $1 AND ($2::varchar IS NULL OR sr.status = $2)
           ORDER BY sr.updated_at DESC""",
        str(current_user["id"]), status,
    )
    return [dict(r) for r in rows]


@router.get("/requests/{request_id}")
async def get_my_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    request = await _get_own_request(conn, request_id, str(current_user["id"]))
    messages = await conn.fetch(
        """SELECT m.id, m.message, m.is_admin, m.created_at,
                  CASE WHEN m.is_admin THEN 'TicketFlow Support' ELSE u.name END AS sender_name
           FROM support_messages m
           JOIN users u ON u.id = m.sender_id
           WHERE m.request_id = $1
           ORDER BY m.created_at ASC""",
        request["id"],
    )
    request["messages"] = [dict(m) for m in messages]
    return request


@router.post("/requests/{request_id}/messages", status_code=201)
async def add_my_message(
    request_id: str,
    body: AddMessage,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    user_id = str(current_user["id"])
    request = await _get_own_request(conn, request_id, user_id)

    if request["status"] in ("resolved", "closed"):
        raise HTTPException(
            status_code=400,
            detail="This request is resolved. Reopen it to send a new message.",
        )

    async with conn.transaction():
        msg = await conn.fetchrow(
            """INSERT INTO support_messages (request_id, sender_id, is_admin, message)
               VALUES ($1, $2, false, $3)
               RETURNING id, message, is_admin, created_at""",
            request["id"], user_id, body.message,
        )
        await conn.execute(
            "UPDATE support_requests SET updated_at = now() WHERE id = $1",
            request["id"],
        )

    result = dict(msg)
    result["sender_name"] = current_user["name"]
    return result


@router.post("/requests/{request_id}/reopen")
async def reopen_my_request(
    request_id: str,
    body: AddMessage,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Reopen a resolved request. The customer must say why it isn't fixed."""
    user_id = str(current_user["id"])
    request = await _get_own_request(conn, request_id, user_id)

    if request["status"] != "resolved":
        raise HTTPException(status_code=400, detail="Only resolved requests can be reopened")

    async with conn.transaction():
        await conn.execute(
            """UPDATE support_requests
               SET status = 'open', resolved_at = NULL, updated_at = now()
               WHERE id = $1""",
            request["id"],
        )
        await conn.execute(
            """INSERT INTO support_messages (request_id, sender_id, is_admin, message)
               VALUES ($1, $2, false, $3)""",
            request["id"], user_id, body.message,
        )

    return {"id": str(request["id"]), "status": "open"}
