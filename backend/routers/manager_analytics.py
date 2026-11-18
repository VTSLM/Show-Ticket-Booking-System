"""
Manager / Organizer analytics dashboard API.

GET /api/manager/insights?days=30&event_id=<uuid>
GET /api/manager/insights?start=2026-11-01&end=2026-11-15
GET /api/manager/insights/event/<event_id>?days=30        (one event: shows, ratings, reviews)

A manager sees only their own organization's events; an admin sees all.
The calculations live in services/manager_analytics.py.
"""
import uuid
from datetime import date
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from database import get_conn
from dependencies import require_role
from services.manager_analytics import build_event_detail, build_overview, resolve_range

# Note: the path avoids the word "analytics" — ad/privacy blockers block URLs like /analytics/events.
router = APIRouter(prefix="/api/manager/insights", tags=["manager-analytics"])


def _owner(user: dict) -> Optional[str]:
    """None for admins (see every organization), else the manager's own user id."""
    return None if "admin" in (user.get("roles") or []) else str(user["id"])


def _range(days: int, start: Optional[date], end: Optional[date]):
    try:
        return resolve_range(days, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("")
async def manager_analytics(
    days: int = Query(30, ge=1, le=366),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    event_id: Optional[str] = Query(None),
    user: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    d_from, d_to = _range(days, start, end)
    owner = _owner(user)
    if event_id:
        try:
            event_id = str(uuid.UUID(event_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid event_id")

    has_org = True
    if owner is not None:
        has_org = bool(await conn.fetchval(
            "SELECT 1 FROM organizer_profiles WHERE user_id = $1 LIMIT 1", user["id"]))

    return await build_overview(conn, owner, event_id, d_from, d_to, has_org=has_org)


@router.get("/event/{event_id}")
async def event_analytics(
    event_id: str,
    days: int = Query(30, ge=1, le=366),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    user: dict = Depends(require_role("manager", "admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Per-event (per-movie) detail: header info, every show with its sales, rating breakdown, latest reviews."""
    try:
        event_id = str(uuid.UUID(event_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Event not found")
    d_from, d_to = _range(days, start, end)

    detail = await build_event_detail(conn, _owner(user), event_id, d_from, d_to)
    if detail is None:  # not found, or belongs to another organization
        raise HTTPException(status_code=404, detail="Event not found")
    return detail
