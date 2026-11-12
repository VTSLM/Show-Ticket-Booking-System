# routers/support_admin.py
# Customer Care — Admin side (Hari, Sprint 2)
#
# Items 5, 6, 7:
#   5 — Admin dashboard: list all tickets, filter by status / category / search
#   6 — Reply to tickets / change status (conversation thread)
#   7 — Email notification to customer on admin reply
#
# Auth: require_role("admin", "manager")
# Customer side → routers/support.py (Tirth's work)

from typing import Literal, Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import require_role
from services.support_email_service import send_admin_reply_notification

router = APIRouter(prefix="/api/admin/support", tags=["support-admin"])

# ── Types ─────────────────────────────────────────────────────────────────────

SupportStatus = Literal["open", "in_progress", "resolved", "closed"]


class AdminReplyBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    status: Optional[SupportStatus] = None   # optional status change with the reply


class StatusChangeBody(BaseModel):
    status: SupportStatus


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_request_or_404(request_id: str, conn: asyncpg.Connection) -> dict:
    row = await conn.fetchrow(
        """
        SELECT sr.*,
               u.name  AS user_name,
               u.email AS user_email,
               (SELECT bk.booking_number
                  FROM bookings bk
                 WHERE bk.id = sr.booking_id) AS booking_number
        FROM support_requests sr
        JOIN users u ON u.id = sr.user_id
        WHERE sr.id = $1
        """,
        request_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Support request not found")
    return dict(row)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/requests")
async def list_all_requests(
    status: Optional[SupportStatus] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin: dict = Depends(require_role("admin", "manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    List all support requests (admin view).
    Optional filters: status, category, search (subject or request_number).
    Sorted: open first, then in_progress, resolved, closed; newest first within each group.
    """
    conditions: list[str] = []
    params: list = []

    if status:
        params.append(status)
        conditions.append(f"sr.status = ${len(params)}")
    if category:
        params.append(category)
        conditions.append(f"sr.category = ${len(params)}")
    if search:
        params.append(f"%{search}%")
        n = len(params)
        conditions.append(f"(sr.subject ILIKE ${n} OR sr.request_number ILIKE ${n})")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    rows = await conn.fetch(
        f"""
        SELECT sr.id, sr.request_number, sr.category, sr.subject,
               sr.status, sr.priority, sr.created_at, sr.updated_at,
               u.name  AS user_name,
               u.email AS user_email,
               (SELECT COUNT(*) FROM support_messages sm WHERE sm.request_id = sr.id)
                   AS message_count,
               (SELECT sm2.is_admin
                  FROM support_messages sm2
                 WHERE sm2.request_id = sr.id
                 ORDER BY sm2.created_at DESC
                 LIMIT 1) AS last_reply_by_admin
        FROM support_requests sr
        JOIN users u ON u.id = sr.user_id
        {where}
        ORDER BY
            CASE sr.status
                WHEN 'open'        THEN 0
                WHEN 'in_progress' THEN 1
                WHEN 'resolved'    THEN 2
                ELSE                    3
            END,
            sr.created_at DESC
        """,
        *params,
    )
    return [dict(r) for r in rows]


@router.get("/requests/{request_id}")
async def get_request_detail(
    request_id: str,
    _: dict = Depends(require_role("admin", "manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Get one support request with full message thread (admin view)."""
    request = await _get_request_or_404(request_id, conn)

    messages = await conn.fetch(
        """
        SELECT sm.id, sm.message, sm.is_admin, sm.created_at,
               u.name AS sender_name
        FROM support_messages sm
        JOIN users u ON u.id = sm.sender_id
        WHERE sm.request_id = $1
        ORDER BY sm.created_at
        """,
        request_id,
    )
    request["messages"] = [dict(m) for m in messages]
    return request


@router.post("/requests/{request_id}/reply")
async def admin_reply(
    request_id: str,
    body: AdminReplyBody,
    admin: dict = Depends(require_role("admin", "manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Admin replies to a support request.
    Optionally changes status (e.g. open → in_progress, in_progress → resolved).
    Sends an email notification to the customer (fire-and-forget; never raises on failure).
    """
    request = await _get_request_or_404(request_id, conn)

    if request["status"] == "closed":
        raise HTTPException(status_code=400, detail="Cannot reply to a closed request")

    # Insert message
    msg_row = await conn.fetchrow(
        """
        INSERT INTO support_messages (request_id, sender_id, is_admin, message)
        VALUES ($1, $2, true, $3)
        RETURNING id, message, is_admin, created_at
        """,
        request_id,
        admin["id"],
        body.message.strip(),
    )

    # Update status + timestamp
    new_status = body.status or request["status"]
    if new_status == "resolved" and request["status"] != "resolved":
        await conn.execute(
            "UPDATE support_requests SET updated_at=now(), status=$1, resolved_at=now() WHERE id=$2",
            new_status, request_id,
        )
    else:
        await conn.execute(
            "UPDATE support_requests SET updated_at=now(), status=$1 WHERE id=$2",
            new_status, request_id,
        )

    # Email customer (fire-and-forget — never block the response)
    try:
        await send_admin_reply_notification(
            user_email=request["user_email"],
            user_name=request["user_name"],
            subject=request["subject"],
            request_number=request["request_number"],
            admin_message=body.message.strip(),
            new_status=new_status,
        )
    except Exception as exc:
        print(f"[support_admin] email to customer failed: {exc}")

    return {
        "id": str(msg_row["id"]),
        "message": msg_row["message"],
        "is_admin": True,
        "sender_name": admin["name"],
        "created_at": msg_row["created_at"].isoformat(),
        "new_status": new_status,
    }


@router.patch("/requests/{request_id}/status")
async def change_status(
    request_id: str,
    body: StatusChangeBody,
    _: dict = Depends(require_role("admin", "manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Change a request's status without adding a message."""
    await _get_request_or_404(request_id, conn)

    if body.status == "resolved":
        await conn.execute(
            "UPDATE support_requests SET status=$1, updated_at=now(), resolved_at=now() WHERE id=$2",
            body.status, request_id,
        )
    else:
        await conn.execute(
            "UPDATE support_requests SET status=$1, updated_at=now() WHERE id=$2",
            body.status, request_id,
        )
    return {"status": body.status}
