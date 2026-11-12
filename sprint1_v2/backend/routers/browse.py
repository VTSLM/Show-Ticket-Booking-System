from fastapi import APIRouter, Depends, Query
from typing import Optional
import asyncpg
from database import get_conn

router = APIRouter(prefix="/api/browse", tags=["browse"])

@router.get("/shows")
async def browse_shows(
    city: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date: Optional[str] = Query(None),  # YYYY-MM-DD
    conn: asyncpg.Connection = Depends(get_conn)
):
    filters = ["s.status='scheduled'", "e.status='published'", "s.start_time > now()"]
    params = []
    idx = 1

    if city:
        filters.append(f"lower(v.city) = lower(${idx})")
        params.append(city)
        idx += 1
    if event_type:
        filters.append(f"e.event_type = ${idx}")
        params.append(event_type)
        idx += 1
    if language:
        filters.append(f"lower(e.language) = lower(${idx})")
        params.append(language)
        idx += 1
    if search:
        filters.append(f"(lower(e.title) LIKE lower(${idx}) OR lower(v.name) LIKE lower(${idx}))")
        params.append(f"%{search}%")
        idx += 1
    if date:
        filters.append(f"date(s.start_time) = ${idx}::date")
        params.append(date)
        idx += 1

    where = " AND ".join(filters)
    rows = await conn.fetch(
        f"""SELECT s.id as show_id, s.start_time, COALESCE(MIN(ss.price), s.base_price) as base_price, s.status as show_status,
                   e.id as event_id, e.title, e.event_type, e.language, e.genre, e.duration_minutes,
                   e.poster_url, e.description,
                   v.id as venue_id, v.name as venue_name, v.city, v.address,
                   sc.name as screen_name, sc.capacity,
                   COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                   COUNT(ss.id) as total_seats
            FROM shows s
            JOIN events e ON e.id = s.event_id
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            LEFT JOIN show_seats ss ON ss.show_id = s.id
            WHERE {where}
            GROUP BY s.id, e.id, v.id, sc.id
            ORDER BY s.start_time ASC
            LIMIT 100""",
        *params
    )
    return [dict(r) for r in rows]


@router.get("/shows/{show_id}")
async def get_show_details(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    row = await conn.fetchrow(
        """SELECT s.id as show_id, s.start_time, COALESCE(MIN(ss.price), s.base_price) as base_price, s.status as show_status,
                  e.id as event_id, e.title, e.event_type, e.language, e.genre,
                  e.duration_minutes, e.poster_url, e.description,
                  v.id as venue_id, v.name as venue_name, v.city, v.address,
                  sc.name as screen_name, sc.capacity,
                  COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                  COUNT(ss.id) as total_seats
           FROM shows s
           JOIN events e ON e.id=s.event_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           LEFT JOIN show_seats ss ON ss.show_id=s.id
           WHERE s.id=$1 AND e.status='published' AND s.status='scheduled'
           GROUP BY s.id, e.id, v.id, sc.id""",
        show_id
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Show not found")
    return dict(row)


@router.get("/cities")
async def list_cities(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch("""SELECT DISTINCT v.city
           FROM venues v
           JOIN screens sc ON sc.venue_id = v.id
           JOIN shows s ON s.screen_id = sc.id
           JOIN events e ON e.id = s.event_id
           WHERE s.status='scheduled' AND s.start_time > now()
             AND e.status='published'
           ORDER BY v.city""")
    return [r["city"] for r in rows]


@router.get("/event-types")
async def list_event_types(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT DISTINCT e.event_type FROM events e
           JOIN shows s ON s.event_id=e.id
           WHERE s.status='scheduled' AND s.start_time > now()
             AND e.status='published'"""
    )
    return [r["event_type"] for r in rows]
