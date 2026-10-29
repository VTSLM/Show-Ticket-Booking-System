from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import HTTPException, status
from app.database import execute, fetch_all, fetch_one
from app.models import ShowCreateRequest, ShowHandoffResponse
from app.services.seat_service import get_screen_seat_info

async def list_shows() -> List[dict]:
    query = """
        SELECT sh.id::text, sh.event_id::text, sh.screen_id::text,
               sh.start_time, sh.end_time, sh.status::text,
               sh.created_at, sh.updated_at,
               e.title as event_title, e.event_type::text as event_type, e.poster_url as event_poster_url,
               v.id::text as venue_id, v.name as venue_name,
               sc.name as screen_name, sc.capacity as seat_count,
               (EXISTS (
                   SELECT 1 FROM show_seats ss
                   WHERE ss.show_id = sh.id AND ss.price > 0
               )) as pricing_ready
        FROM shows sh
        JOIN events e ON e.id = sh.event_id
        JOIN screens sc ON sc.id = sh.screen_id
        JOIN venues v ON v.id = sc.venue_id
        ORDER BY sh.start_time DESC;
    """
    return await fetch_all(query)

async def get_show_by_id(show_id: str) -> Optional[dict]:
    query = """
        SELECT sh.id::text, sh.event_id::text, sh.screen_id::text,
               sh.start_time, sh.end_time, sh.status::text,
               sh.created_at, sh.updated_at,
               e.title as event_title, e.event_type::text as event_type, e.poster_url as event_poster_url,
               v.id::text as venue_id, v.name as venue_name,
               sc.name as screen_name, sc.capacity as seat_count,
               (EXISTS (
                   SELECT 1 FROM show_seats ss
                   WHERE ss.show_id = sh.id AND ss.price > 0
               )) as pricing_ready
        FROM shows sh
        JOIN events e ON e.id = sh.event_id
        JOIN screens sc ON sc.id = sh.screen_id
        JOIN venues v ON v.id = sc.venue_id
        WHERE sh.id = $1::uuid;
    """
    return await fetch_one(query, show_id)

async def check_scheduling_conflict(screen_id: str, start_time: datetime, end_time: datetime, exclude_show_id: Optional[str] = None) -> bool:
    """
    Checks if another scheduled show occupies the screen in an overlapping time window.
    Two intervals [s1, e1] and [s2, e2] overlap if (s1 < e2) AND (e1 > s2).
    """
    query = """
        SELECT id::text
        FROM shows
        WHERE screen_id = $1::uuid
          AND status = 'scheduled'
          AND start_time < $3
          AND end_time > $2
    """
    args = [screen_id, start_time, end_time]
    if exclude_show_id:
        query += " AND id <> $4::uuid"
        args.append(exclude_show_id)
    query += " LIMIT 1;"

    conflict = await fetch_one(query, *args)
    return conflict is not None

async def create_show(data: ShowCreateRequest) -> dict:
    # 1. Verify event exists
    event_query = "SELECT id::text, title, duration_minutes FROM events WHERE id = $1::uuid;"
    event_row = await fetch_one(event_query, data.event_id)
    if not event_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {data.event_id} does not exist."
        )

    # 2. Verify screen exists
    screen_query = "SELECT id::text, venue_id::text, name, capacity FROM screens WHERE id = $1::uuid;"
    screen_row = await fetch_one(screen_query, data.screen_id)
    if not screen_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screen with ID {data.screen_id} does not exist."
        )

    # 3. Determine end_time if not explicitly provided
    start_time = data.start_time
    if data.end_time:
        end_time = data.end_time
    else:
        duration = event_row.get("duration_minutes") or 120
        # Add 15 min buffer between shows
        end_time = start_time + timedelta(minutes=duration + 15)

    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Show end_time must be strictly after start_time."
        )

    # 4. Check scheduling conflicts
    has_conflict = await check_scheduling_conflict(data.screen_id, start_time, end_time)
    if has_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scheduling conflict: Another show is already scheduled for this screen during this time window."
        )

    # 5. Insert show into Supabase 'shows' table
    insert_query = """
        INSERT INTO shows (event_id, screen_id, start_time, end_time, status)
        VALUES ($1::uuid, $2::uuid, $3, $4, 'scheduled'::show_status)
        RETURNING id::text, event_id::text, screen_id::text, start_time, end_time, status::text, created_at, updated_at;
    """
    created = await fetch_one(insert_query, data.event_id, data.screen_id, start_time, end_time)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist show record to database."
        )

    # Enrich response
    seat_info = await get_screen_seat_info(data.screen_id)
    created["event_title"] = event_row["title"]
    created["screen_name"] = screen_row["name"]
    created["venue_id"] = screen_row["venue_id"]
    created["seat_count"] = seat_info.seat_count
    created["pricing_ready"] = False
    return created

async def get_show_handoff(show_id: str) -> ShowHandoffResponse:
    show = await get_show_by_id(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with ID {show_id} not found."
        )

    seat_info = await get_screen_seat_info(show["screen_id"])
    seat_count = seat_info.seat_count
    event_id = show["event_id"]
    screen_id = show["screen_id"]

    pricing_route = f"/pricing?show_id={show_id}&event_id={event_id}&screen_id={screen_id}&seat_count={seat_count}"

    return ShowHandoffResponse(
        show_id=show["id"],
        event_id=event_id,
        event_title=show.get("event_title") or "",
        venue_id=show.get("venue_id") or "",
        venue_name=show.get("venue_name") or "",
        screen_id=screen_id,
        screen_name=show.get("screen_name") or "",
        start_time=show["start_time"],
        end_time=show["end_time"],
        status=show["status"],
        seat_count=seat_count,
        pricing_ready=show.get("pricing_ready", False),
        pricing_route=pricing_route,
        integration_notes="Handoff to Feature 04: Seat categories and pricing must be configured before show is publicly bookable."
    )

async def delete_show(show_id: str) -> dict:
    show = await get_show_by_id(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with ID {show_id} not found."
        )

    # Check for active bookings
    booking_check = await fetch_one(
        "SELECT COUNT(*) as count FROM bookings WHERE show_id = $1::uuid;",
        show_id
    )
    if booking_check and booking_check["count"] > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete show because active customer bookings exist for it."
        )

    # Delete show_seats for this show
    await execute("DELETE FROM show_seats WHERE show_id = $1::uuid;", show_id)
    # Delete show
    await execute("DELETE FROM shows WHERE id = $1::uuid;", show_id)
    return {"message": "Show successfully deleted", "id": show_id}
