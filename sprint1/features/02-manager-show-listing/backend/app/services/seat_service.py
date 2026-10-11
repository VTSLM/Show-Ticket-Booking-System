from typing import Optional
from fastapi import HTTPException, status
from app.database import fetch_one
from app.models import SeatCountInfo

async def get_screen_seat_info(screen_id: str) -> SeatCountInfo:
    """
    Derives authoritative seat count for a screen based on:
    1. Count of physical seat records in 'seats'
    2. Approved capacity in 'layouts' (if configured)
    3. Baseline screen capacity in 'screens.capacity'
    """
    # 1. Screen and Venue lookup
    screen_query = """
        SELECT s.id::text, s.venue_id::text, s.name as screen_name, s.capacity,
               v.name as venue_name
        FROM screens s
        JOIN venues v ON v.id = s.venue_id
        WHERE s.id = $1::uuid;
    """
    screen_row = await fetch_one(screen_query, screen_id)
    if not screen_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screen with ID {screen_id} not found."
        )

    screen_capacity = screen_row["capacity"]
    screen_name = screen_row["screen_name"]
    venue_id = screen_row["venue_id"]
    venue_name = screen_row["venue_name"]

    # 2. Count physical seats in 'seats' table
    seats_query = """
        SELECT count(*)::int as seat_count
        FROM seats
        WHERE screen_id = $1::uuid;
    """
    seats_res = await fetch_one(seats_query, screen_id)
    seats_table_count = seats_res["seat_count"] if seats_res else 0

    # 3. Check 'layouts' table if present
    layout_capacity: Optional[int] = None
    try:
        layout_query = """
            SELECT approved_capacity
            FROM layouts
            WHERE screen_id = $1::uuid
            ORDER BY updated_at DESC
            LIMIT 1;
        """
        layout_res = await fetch_one(layout_query, screen_id)
        if layout_res and layout_res.get("approved_capacity"):
            layout_capacity = int(layout_res["approved_capacity"])
    except Exception:
        # Layouts table might be optional or empty
        layout_capacity = None

    # Determine primary seat count and authoritative source
    if seats_table_count > 0:
        primary_count = seats_table_count
        source = "seats_table"
    elif layout_capacity and layout_capacity > 0:
        primary_count = layout_capacity
        source = "layouts_table"
    else:
        primary_count = screen_capacity
        source = "screens_capacity"

    return SeatCountInfo(
        screen_id=screen_id,
        screen_name=screen_name,
        venue_id=venue_id,
        venue_name=venue_name,
        seat_count=primary_count,
        source=source,
        screen_capacity=screen_capacity,
        seats_table_count=seats_table_count,
        layout_capacity=layout_capacity,
    )
