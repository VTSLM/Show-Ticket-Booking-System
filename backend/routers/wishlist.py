"""
Wishlist (Sprint 2) — logged-in users can save events to watch later.

Table: wishlists (database/migrations/0021_wishlist.sql)
  GET    /api/wishlist            my saved events (with their next upcoming show)
  GET    /api/wishlist/ids        just the saved event ids (used to fill the hearts on Browse)
  POST   /api/wishlist/{event_id} save an event
  DELETE /api/wishlist/{event_id} remove an event
"""
import uuid as uuid_module

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from database import get_conn
from dependencies import get_current_user

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


@router.get("")
async def my_wishlist(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        SELECT e.id AS event_id, e.title, e.event_type, e.language, e.genre,
               e.duration_minutes, e.poster_url, e.status AS event_status,
               w.created_at AS added_at,
               ns.next_show_time, ns.shows_count,
               ns.venue_name, ns.city, ns.latitude, ns.longitude
        FROM wishlists w
        JOIN events e ON e.id = w.event_id
        LEFT JOIN LATERAL (
            SELECT s.start_time AS next_show_time,
                   (SELECT COUNT(*) FROM shows s2 WHERE s2.event_id = e.id AND s2.status = 'scheduled' AND s2.start_time > now()) AS shows_count,
                   v.name AS venue_name, v.city, v.latitude, v.longitude
            FROM shows s
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            WHERE s.event_id = e.id AND s.status = 'scheduled' AND s.start_time > now()
            ORDER BY s.start_time ASC
            LIMIT 1
        ) ns ON true
        WHERE w.user_id = $1
        ORDER BY w.created_at DESC
        """,
        current_user["id"],
    )
    items = []
    for r in rows:
        item = dict(r)
        item["event_id"] = str(item["event_id"])
        item["shows_count"] = int(item["shows_count"] or 0)
        # Bookable = the event is published and has at least one upcoming show
        item["is_bookable"] = item["event_status"] == "published" and item["shows_count"] > 0
        items.append(item)
    return items


@router.get("/ids")
async def my_wishlist_ids(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch("SELECT event_id FROM wishlists WHERE user_id = $1", current_user["id"])
    return {"event_ids": [str(r["event_id"]) for r in rows]}


@router.post("/{event_id}")
async def add_to_wishlist(
    event_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    exists = await conn.fetchval("SELECT 1 FROM events WHERE id = $1 AND status = 'published'", event_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Event not found")
    await conn.execute(
        "INSERT INTO wishlists (user_id, event_id) VALUES ($1, $2) ON CONFLICT (user_id, event_id) DO NOTHING",
        current_user["id"], event_id,
    )
    return {"wishlisted": True}


@router.delete("/{event_id}")
async def remove_from_wishlist(
    event_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await conn.execute(
        "DELETE FROM wishlists WHERE user_id = $1 AND event_id = $2",
        current_user["id"], event_id,
    )
    return {"wishlisted": False}
