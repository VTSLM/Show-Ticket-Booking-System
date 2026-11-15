from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import date as dt_date
from difflib import SequenceMatcher
import asyncpg
from database import get_conn
from services.dynamic_pricing import pricing_summary, apply_multiplier

router = APIRouter(prefix="/api/browse", tags=["browse"])


def _fuzzy_score(query: str, *fields: Optional[str]) -> float:
    """
    Returns a relevance score in [0.0, 1.0].
    Matches exact substrings (1.0) as well as spelling typos / partial words (e.g. 'spidy' -> 'Spider-Man').
    """
    q = query.lower().strip()
    if not q:
        return 1.0

    best = 0.0
    for field in fields:
        if not field:
            continue
        text = field.lower()

        # 1. Exact substring match
        if q in text:
            return 1.0

        # 2. Whole-string similarity
        best = max(best, SequenceMatcher(None, q, text).ratio())

        # 3. Word-level & prefix similarity (catches 'spidy' -> 'spider', 'inseption' -> 'inception')
        for word in text.replace("-", " ").replace(":", " ").split():
            if word.startswith(q) or q.startswith(word):
                best = max(best, 0.85)
            else:
                best = max(best, SequenceMatcher(None, q, word).ratio())

    return best


def _with_dynamic_price(item: dict) -> dict:
    """Add the current dynamic 'from' price next to the fixed base price."""
    sold = item.pop("sold_seats", 0) or 0
    enabled = bool(item.pop("dynamic_pricing", False))
    base = item.get("base_price")
    if base is None:                           # zone-only show: no seat prices to adjust
        item.update(current_price=None, price_change_pct=0, pricing_reasons=[])
        return item
    pricing = pricing_summary(item["start_time"], sold, item.get("total_seats") or 0, enabled,
                              str(item.get("event_type") or "movie"))
    item["current_price"] = float(apply_multiplier(base, pricing["multiplier"]))
    item["price_change_pct"] = pricing["change_pct"]
    item["pricing_reasons"] = pricing["reasons"]
    return item


async def _attach_ratings(conn: asyncpg.Connection, items: list) -> None:
    """Add avg_rating and review_count (public reviews only) to every show dict."""
    event_ids = list({i["event_id"] for i in items if i.get("event_id")})
    stats = {}
    if event_ids:
        rows = await conn.fetch(
            """
            SELECT r.event_id, ROUND(AVG(r.rating)::numeric, 1) AS avg_rating, COUNT(*) AS review_count
            FROM reviews r
            WHERE r.event_id = ANY($1)
              AND r.is_draft = false
              AND (r.scheduled_for IS NULL OR r.scheduled_for <= now())
            GROUP BY r.event_id
            """,
            event_ids,
        )
        stats = {str(r["event_id"]): r for r in rows}
    for item in items:
        st = stats.get(str(item.get("event_id")))
        item["avg_rating"] = float(st["avg_rating"]) if st else None
        item["review_count"] = int(st["review_count"]) if st else 0


@router.get("/shows")
async def browse_shows(
    city: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date: Optional[str] = Query(None),  # YYYY-MM-DD
    sort_by: Optional[str] = Query("time_asc"),  # time_asc | price_asc | price_desc | seats_desc | rating_desc
    conn: asyncpg.Connection = Depends(get_conn),
):
    filters = ["s.status='scheduled'", "e.status='published'", "s.start_time > now()"]
    params = []
    idx = 1

    if city:
        filters.append(f"lower(v.city) = lower(${idx})")
        params.append(city.strip())
        idx += 1
    if event_type:
        filters.append(f"lower(e.event_type::text) = lower(${idx})")
        params.append(event_type.strip())
        idx += 1
    if language:
        filters.append(f"lower(e.language) = lower(${idx})")
        params.append(language.strip())
        idx += 1
    if genre:
        filters.append(f"lower(COALESCE(e.genre, '')) LIKE lower(${idx})")
        params.append(f"%{genre.strip()}%")
        idx += 1
    if date:
        try:
            parsed_date = dt_date.fromisoformat(date.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")
        filters.append(f"date(s.start_time) = ${idx}")
        params.append(parsed_date)
        idx += 1


    where = " AND ".join(filters)
    rows = await conn.fetch(
        f"""SELECT s.id as show_id, s.start_time, MIN(ss.price) as base_price, s.status as show_status, s.dynamic_pricing,
                   e.id as event_id, e.title, e.event_type, e.language, e.genre, e.duration_minutes,
                   e.poster_url, e.description, op.legal_name as organizer_name,
                   v.id as venue_id, v.name as venue_name, v.city, v.address,
                   sc.name as screen_name, sc.capacity,
                   COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                   COUNT(ss.id) FILTER (WHERE ss.status='booked') as sold_seats,
                   COUNT(ss.id) as total_seats
            FROM shows s
            JOIN events e ON e.id = s.event_id
            LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            LEFT JOIN show_seats ss ON ss.show_id = s.id
            WHERE {where}
            GROUP BY s.id, e.id, v.id, sc.id, op.legal_name
            ORDER BY s.start_time ASC
            LIMIT 100""",
        *params
    )

    results = [_with_dynamic_price(dict(r)) for r in rows]

    # Apply fuzzy spelling-tolerant search across title, venue, city, genre, and language
    if search and search.strip():
        q = search.strip()
        scored = []
        for item in results:
            score = _fuzzy_score(
                q,
                item.get("title"),
                item.get("venue_name"),
                item.get("city"),
                item.get("genre"),
                item.get("language"),
            )
            if score >= 0.55:
                item["relevance"] = round(score, 3)
                scored.append(item)

        if sort_by == "time_asc":
            scored.sort(key=lambda x: (-x["relevance"], x["start_time"]))
        results = scored

    # Ratings shown on each card (and used by the "Top rated" sort)
    await _attach_ratings(conn, results)

    # Sort by the price customers actually pay now (dynamic), by seats, or by rating
    if sort_by == "rating_desc":
        results.sort(key=lambda x: (
            x["avg_rating"] is None,
            -(x["avg_rating"] or 0),
            -x["review_count"],
            x["start_time"],
        ))
    elif sort_by == "price_asc":
        results.sort(key=lambda x: (x["current_price"] is None, x["current_price"] or 0, x["start_time"]))
    elif sort_by == "price_desc":
        results.sort(key=lambda x: (x["current_price"] is None, -(x["current_price"] or 0), x["start_time"]))
    elif sort_by == "seats_desc":
        results.sort(key=lambda x: (-(x["available_seats"] or 0), x["start_time"]))

    return results[:100]


@router.get("/shows/{show_id}")
async def get_show_details(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    row = await conn.fetchrow(
        """SELECT s.id as show_id, s.start_time, MIN(ss.price) as base_price, s.status as show_status, s.dynamic_pricing,
                  e.id as event_id, e.title, e.event_type, e.language, e.genre,
                  e.duration_minutes, e.poster_url, e.description, op.legal_name as organizer_name,
                  v.id as venue_id, v.name as venue_name, v.city, v.address,
                  sc.name as screen_name, sc.capacity,
                  COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                  COUNT(ss.id) FILTER (WHERE ss.status='booked') as sold_seats,
                  COUNT(ss.id) as total_seats
           FROM shows s
           JOIN events e ON e.id=s.event_id
           LEFT JOIN organizer_profiles op ON op.id=e.organizer_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           LEFT JOIN show_seats ss ON ss.show_id=s.id
           WHERE s.id=$1 AND e.status='published' AND s.status='scheduled'
           GROUP BY s.id, e.id, v.id, sc.id, op.legal_name""",
        show_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Show not found")
    return _with_dynamic_price(dict(row))


@router.get("/cities")
async def list_cities(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch("SELECT DISTINCT city FROM venues WHERE city IS NOT NULL ORDER BY city")
    return [r["city"] for r in rows]


@router.get("/event-types")
async def list_event_types(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT DISTINCT e.event_type FROM events e
           JOIN shows s ON s.event_id=e.id
           WHERE s.status='scheduled' AND s.start_time > now()"""
    )
    return [r["event_type"] for r in rows]


@router.get("/languages")
async def list_languages(conn: asyncpg.Connection = Depends(get_conn)):
    rows = await conn.fetch(
        """SELECT DISTINCT e.language FROM events e
           JOIN shows s ON s.event_id=e.id
           WHERE e.language IS NOT NULL AND e.language <> ''
             AND s.status='scheduled' AND s.start_time > now()
           ORDER BY e.language"""
    )
    return [r["language"] for r in rows]