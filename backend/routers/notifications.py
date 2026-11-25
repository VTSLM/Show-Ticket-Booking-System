"""
Endpoints for user and admin in-app notifications.
Allows fetching unread notifications and marking them as read.
"""
import json
import asyncpg
from fastapi import APIRouter, Depends
from database import get_conn
from dependencies import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def get_my_notifications(
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Returns the customer's notifications with unread count.
    """
    user_id = str(current_user["id"])
    rows = await conn.fetch(
        """
        SELECT id, event_name, payload, read_at, created_at
        FROM notifications
        WHERE user_id = $1::uuid
        ORDER BY created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    unread_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id = $1::uuid AND read_at IS NULL
        """,
        user_id,
    )

    notifications = []
    for row in rows:
        item = dict(row)
        if isinstance(item.get("payload"), str):
            try:
                item["payload"] = json.loads(item["payload"])
            except json.JSONDecodeError:
                item["payload"] = {}
        notifications.append(item)

    return {
        "notifications": notifications,
        "unread_count": unread_count or 0,
    }


@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Marks an individual notification as read.
    """
    await conn.execute(
        """
        UPDATE notifications
        SET read_at = now()
        WHERE id = $1::uuid AND user_id = $2::uuid AND read_at IS NULL
        """,
        notification_id,
        str(current_user["id"]),
    )
    return {"status": "success"}


@router.patch("/read-all")
async def mark_all_notifications_as_read(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Marks all notifications for current user as read.
    """
    await conn.execute(
        """
        UPDATE notifications
        SET read_at = now()
        WHERE user_id = $1::uuid AND read_at IS NULL
        """,
        str(current_user["id"]),
    )
    return {"status": "success"}
