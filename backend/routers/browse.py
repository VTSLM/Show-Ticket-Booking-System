from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import date as dt_date
from difflib import SequenceMatcher
import asyncpg
from database import get_conn
from services.dynamic_pricing import pricing_summary, apply_multiplier
import json
from services.terms_service import resolve_show_terms
from services.geo_service import DEFAULT_RADIUS_KM, INDIA_CITIES, venues_within

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
    sort_by: Optional[str] = Query("time_asc"),  # time_asc | price_asc | price_desc | seats_desc | rating_desc | distance_asc
    # "Near me": send lat + lng to get only shows at venues within radius_km (default 100 km)
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0, le=500),
    conn: asyncpg.Connection = Depends(get_conn),
):
    # (when called directly, unset Query() defaults are not numbers: treat them as "not sent")
    lat = lat if isinstance(lat, (int, float)) else None
    lng = lng if isinstance(lng, (int, float)) else None
    radius_km = radius_km if isinstance(radius_km, (int, float)) else DEFAULT_RADIUS_KM
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=400, detail="Send both lat and lng")

    filters = ["s.status='scheduled'", "e.status='published'", "s.start_time > now()"]
    params = []
    idx = 1

    # Nearby mode: find the venues inside the radius, then join their distances into the query
    nearby = lat is not None
    near_join = ""
    near_select = ""
    agg_order = "s.start_time ASC"
    if nearby:
        venue_rows = await conn.fetch("SELECT id, city, latitude, longitude FROM venues")
        near = venues_within([dict(v) for v in venue_rows], lat, lng, radius_km)
        if not near:
            return []
        near_join = (
            f"JOIN unnest(${idx}::uuid[], ${idx + 1}::float8[], ${idx + 2}::boolean[]) "
            "AS nv(venue_id, dist_km, exact) ON nv.venue_id = v.id"
        )
        params += [
            [str(n["venue_id"]) for n in near],
            [n["distance_km"] for n in near],
            [n["exact"] for n in near],
        ]
        idx += 3
        agg_order = "nv.dist_km ASC, s.start_time ASC"  # the card shows the NEAREST venue
        near_select = (
            ",\n                   MIN(nv.dist_km) as distance_km,"
            f"\n                   (ARRAY_AGG(nv.exact ORDER BY {agg_order}))[1] as distance_exact"
        )

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
    if genre and isinstance(genre, str):
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

    order_map = {
        "time_asc": "MIN(s.start_time) ASC",
        "price_asc": "MIN(ss.price) ASC NULLS LAST, MIN(s.start_time) ASC",
        "price_desc": "MIN(ss.price) DESC NULLS LAST, MIN(s.start_time) ASC",
        "seats_desc": "COUNT(ss.id) FILTER (WHERE ss.status='available') DESC, MIN(s.start_time) ASC",
    }
    if nearby:
        order_map["distance_asc"] = "MIN(nv.dist_km) ASC, MIN(s.start_time) ASC"
    order_clause = order_map.get(sort_by or "time_asc", "MIN(s.start_time) ASC")

    where = " AND ".join(filters)
    rows = await conn.fetch(
        f"""SELECT e.id as event_id,
                   MIN(s.id::text)::uuid as show_id,
                   MIN(s.start_time) as start_time,
                   MIN(ss.price) as base_price,
                   'scheduled' as show_status,
                   BOOL_OR(COALESCE(s.dynamic_pricing, false)) as dynamic_pricing,
                   e.title, e.event_type, e.language, e.genre, e.duration_minutes,
                   e.poster_url, e.backdrop_url, e.description,
                   op.legal_name as organizer_name,
                   COUNT(DISTINCT v.id) as theatres_count,
                   COUNT(DISTINCT s.id) as shows_count,
                   (ARRAY_AGG(v.name ORDER BY {agg_order}))[1] as venue_name,
                   (ARRAY_AGG(v.city ORDER BY {agg_order}))[1] as city,
                   (ARRAY_AGG(v.address ORDER BY {agg_order}))[1] as address,
                   (ARRAY_AGG(sc.name ORDER BY {agg_order}))[1] as screen_name,
                   SUM(DISTINCT sc.capacity) as capacity,
                   COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                   COUNT(ss.id) FILTER (WHERE ss.status='booked') as sold_seats,
                   COUNT(ss.id) as total_seats{near_select}
            FROM shows s
            JOIN events e ON e.id = s.event_id
            LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            {near_join}
            LEFT JOIN show_seats ss ON ss.show_id = s.id
            WHERE {where}
            GROUP BY e.id, op.legal_name
            ORDER BY {order_clause}
            LIMIT 100""",
        *params
    )

    results = [_with_dynamic_price(dict(r)) for r in rows]
    if nearby:
        for item in results:
            item["distance_km"] = round(float(item["distance_km"]), 2)

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
    elif sort_by == "distance_asc" and nearby:
        results.sort(key=lambda x: (x["distance_km"], x["start_time"]))

    return results[:100]



@router.get("/shows/{show_id}")
async def get_show_details(show_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    row = await conn.fetchrow(
        """SELECT s.id as show_id, s.start_time, s.end_time, MIN(ss.price) as base_price, s.status as show_status, s.dynamic_pricing,
                  s.terms_and_conditions as show_terms,
                  e.id as event_id, e.title, e.event_type, e.language, e.genre,
                  e.duration_minutes, e.poster_url, e.backdrop_url, e.description,
                  e.cast_crew, e.artists, e.formats, e.certificate, e.release_date,
                  e.terms_and_conditions as event_terms,
                  e.imdb_score, e.metacritic_score, e.age_rating, e.match_rate,
                  op.legal_name as organizer_name,
                  v.id as venue_id, v.name as venue_name, v.city, v.address,
                  sc.id as screen_id, sc.name as screen_name, sc.capacity,
                  sc.layout_type, sc.stage_position, sc.layout_config,
                  COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                  COUNT(ss.id) FILTER (WHERE ss.status='booked') as sold_seats,
                  COUNT(ss.id) as total_seats
           FROM shows s
           JOIN events e ON e.id=s.event_id
           LEFT JOIN organizer_profiles op ON op.id=e.organizer_id
           JOIN screens sc ON sc.id=s.screen_id
           JOIN venues v ON v.id=sc.venue_id
           LEFT JOIN show_seats ss ON ss.show_id=s.id
           WHERE s.id=$1::uuid AND e.status='published' AND s.status='scheduled'
           GROUP BY s.id, e.id, v.id, sc.id, op.legal_name""",
        show_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Show not found")

    res = _with_dynamic_price(dict(row))
    # Parse JSON fields if strings
    for field in ("cast_crew", "artists", "layout_config"):
        if isinstance(res.get(field), str):
            try:
                res[field] = json.loads(res[field])
            except Exception:
                pass

    # Resolve show-specific Terms & Conditions (or TicketFlow System Default)
    terms_text, terms_hash, is_default = resolve_show_terms(
        show_terms=res.get("show_terms"),
        event_terms=res.get("event_terms")
    )
    res["terms_and_conditions"] = terms_text
    res["terms_hash"] = terms_hash
    res["is_default_terms"] = is_default

    # Fetch ratings summary for this event
    if res.get("event_id"):
        rating_row = await conn.fetchrow(
            """SELECT COUNT(id) as review_count, ROUND(AVG(rating), 1) as avg_rating
               FROM reviews WHERE event_id = $1::uuid AND is_draft = false""",
            res["event_id"]
        )
        res["review_count"] = int(rating_row["review_count"]) if rating_row and rating_row["review_count"] else 0
        res["avg_rating"] = float(rating_row["avg_rating"]) if rating_row and rating_row["avg_rating"] else None
    else:
        res["review_count"] = 0
        res["avg_rating"] = None

    # Fetch zones if concert/festival
    zones = await conn.fetch(
        """SELECT id, name, zone_type, total_capacity, booked_count, locked_count,
                  price, color_hex, display_order,
                  GREATEST(0, total_capacity - booked_count - locked_count) as available_capacity
           FROM show_zones WHERE show_id = $1::uuid ORDER BY display_order""",
        show_id
    )
    res["zones"] = [dict(z) for z in zones]

    # Fetch upcoming scheduled shows for this event across all venues & dates
    if res.get("event_id"):
        shows = await conn.fetch(
            """SELECT s.id as show_id, s.start_time, s.end_time, s.base_price, s.status as show_status,
                      v.id as venue_id, v.name as venue_name, v.city, v.address,
                      sc.id as screen_id, sc.name as screen_name, sc.layout_type, sc.stage_position,
                      COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                      COUNT(ss.id) as total_seats
               FROM shows s
               JOIN screens sc ON sc.id = s.screen_id
               JOIN venues v ON v.id = sc.venue_id
               LEFT JOIN show_seats ss ON ss.show_id = s.id
               WHERE s.event_id = $1::uuid AND s.status = 'scheduled' AND s.start_time > NOW()
               GROUP BY s.id, v.id, sc.id
               ORDER BY s.start_time ASC""",
            res["event_id"]
        )
        res["upcoming_shows"] = [dict(s) for s in shows]
    else:
        res["upcoming_shows"] = []

    return res


@router.get("/events/{event_id}")
async def get_event_details(event_id: str, conn: asyncpg.Connection = Depends(get_conn)):
    """
    Dedicated Event Details Endpoint:
    Provides rich event details, cast, artists, rating summary, and upcoming scheduled shows across venues/dates.
    """
    event = await conn.fetchrow(
        """SELECT e.*, op.legal_name as organizer_name
           FROM events e
           LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
           WHERE e.id = $1::uuid AND e.status = 'published'""",
        event_id
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    res = dict(event)
    for field in ("cast_crew", "artists"):
        if isinstance(res.get(field), str):
            try:
                res[field] = json.loads(res[field])
            except Exception:
                pass

    # Reviews summary
    rating_row = await conn.fetchrow(
        """SELECT COUNT(id) as review_count, ROUND(AVG(rating), 1) as avg_rating
           FROM reviews WHERE event_id = $1::uuid AND is_draft = false""",
        event_id
    )
    res["review_count"] = int(rating_row["review_count"]) if rating_row and rating_row["review_count"] else 0
    res["avg_rating"] = float(rating_row["avg_rating"]) if rating_row and rating_row["avg_rating"] else None

    # Resolve event-level terms
    terms_text, terms_hash, is_default = resolve_show_terms(None, res.get("terms_and_conditions"))
    res["terms_and_conditions"] = terms_text
    res["terms_hash"] = terms_hash
    res["is_default_terms"] = is_default

    # Fetch upcoming scheduled shows for this event
    shows = await conn.fetch(
        """SELECT s.id as show_id, s.start_time, s.end_time, s.base_price, s.status as show_status,
                  v.id as venue_id, v.name as venue_name, v.city, v.address,
                  sc.id as screen_id, sc.name as screen_name, sc.layout_type, sc.stage_position,
                  COUNT(ss.id) FILTER (WHERE ss.status='available') as available_seats,
                  COUNT(ss.id) as total_seats
           FROM shows s
           JOIN screens sc ON sc.id = s.screen_id
           JOIN venues v ON v.id = sc.venue_id
           LEFT JOIN show_seats ss ON ss.show_id = s.id
           WHERE s.event_id = $1::uuid AND s.status = 'scheduled' AND s.start_time > NOW()
           GROUP BY s.id, v.id, sc.id
           ORDER BY s.start_time ASC""",
        event_id
    )
    res["upcoming_shows"] = [dict(s) for s in shows]

    return res


@router.get("/india-cities")
async def india_cities():
    """Indian cities with their centre point, for the location picker."""
    return INDIA_CITIES


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