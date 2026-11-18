"""
Read-only tools for the TicketFlow assistant (services/chatbot.py).

Every tool reads the database and returns a small JSON-friendly dict with
in-app links. Tools never change data. Tools about bookings or the wishlist
only ever use the logged-in user's id from the verified login token; the model
cannot pass a user id.
"""
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

import asyncpg

from routers.browse import _attach_ratings, _fuzzy_score, _with_dynamic_price
from routers.cancellations import CANCEL_CUTOFF_HOURS

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
MAX_EVENTS = 8
SHOWS_PER_EVENT = 3
EVENT_TYPES = ("movie", "concert", "theatre", "other")


# ── helpers ──────────────────────────────────────────────────────────────────

def _is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _fmt_time(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.astimezone(IST).strftime("%a %d %b %Y, %I:%M %p IST")


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _money(value: Any) -> Optional[float]:
    return round(float(value), 2) if value is not None else None


def _clip(text: Optional[str], limit: int = 300) -> Optional[str]:
    if not text:
        return text
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _genre_words(genre: Optional[str]) -> set:
    return {w for w in re.split(r"[^a-z]+", (genre or "").lower()) if len(w) > 2}


LOGIN_REQUIRED = {
    "error": "login_required",
    "message": "The user is not logged in. Ask them to log in first.",
    "login_link": "/auth/login",
}


# ── shows and events ─────────────────────────────────────────────────────────

async def _upcoming_shows(
    conn: asyncpg.Connection,
    city: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    event_id: Optional[str] = None,
) -> List[dict]:
    """Upcoming scheduled shows of published events, one row per show, with the current price."""
    filters = ["s.status = 'scheduled'", "e.status = 'published'", "s.start_time > now()"]
    params: list = []

    def add(sql: str, value: Any) -> None:
        params.append(value)
        filters.append(sql.format(n=len(params)))

    if city:
        add("lower(v.city) = lower(${n})", city.strip())
    if event_type and event_type.lower() in EVENT_TYPES:
        add("e.event_type::text = ${n}", event_type.lower())
    if date_from:
        add("(s.start_time AT TIME ZONE 'Asia/Kolkata')::date >= ${n}", date_from)
    if date_to:
        add("(s.start_time AT TIME ZONE 'Asia/Kolkata')::date <= ${n}", date_to)
    if event_id:
        add("e.id = ${n}::uuid", event_id)

    rows = await conn.fetch(
        f"""SELECT s.id AS show_id, s.start_time, s.dynamic_pricing,
                   e.id AS event_id, e.title, e.event_type::text AS event_type,
                   e.language, e.genre, e.duration_minutes,
                   v.name AS venue_name, v.city, v.address,
                   MIN(ss.price) AS base_price,
                   COUNT(ss.id) FILTER (WHERE ss.status = 'available') AS available_seats,
                   COUNT(ss.id) FILTER (WHERE ss.status = 'booked') AS sold_seats,
                   COUNT(ss.id) AS total_seats
            FROM shows s
            JOIN events e ON e.id = s.event_id
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            LEFT JOIN show_seats ss ON ss.show_id = s.id
            WHERE {" AND ".join(filters)}
            GROUP BY s.id, e.id, v.id
            ORDER BY s.start_time ASC
            LIMIT 400""",
        *params,
    )
    return [_with_dynamic_price(dict(r)) for r in rows]


def _show_card(show: dict) -> dict:
    return {
        "show_id": str(show["show_id"]),
        "time": _fmt_time(show["start_time"]),
        "venue": show["venue_name"],
        "city": show["city"],
        "price_from": _money(show.get("current_price")),
        "seats_left": int(show.get("available_seats") or 0),
        "book_link": f"/shows/{show['show_id']}",
    }


def _group_by_event(shows: List[dict]) -> List[dict]:
    events: Dict[str, dict] = {}
    for s in shows:
        key = str(s["event_id"])
        ev = events.get(key)
        if ev is None:
            ev = events[key] = {
                "event_id": key,
                "title": s["title"],
                "type": s["event_type"],
                "genre": s.get("genre"),
                "language": s.get("language"),
                "duration_minutes": s.get("duration_minutes"),
                "link": f"/events/{key}",
                "shows": [],
                "_all": [],
            }
        ev["_all"].append(s)
        if len(ev["shows"]) < SHOWS_PER_EVENT:
            ev["shows"].append(_show_card(s))
    for ev in events.values():
        prices = [p["current_price"] for p in ev["_all"] if p.get("current_price") is not None]
        ev["price_from"] = _money(min(prices)) if prices else None
        ev["upcoming_show_count"] = len(ev.pop("_all"))
    return list(events.values())


async def _with_ratings(conn: asyncpg.Connection, events: List[dict]) -> None:
    await _attach_ratings(conn, events)


async def search_shows(conn, user, *, query=None, city=None, event_type=None,
                       date_from=None, date_to=None, max_price=None, sort="soonest") -> dict:
    d_from, d_to = _parse_date(date_from), _parse_date(date_to)
    shows = await _upcoming_shows(conn, city, event_type, d_from, d_to)

    if query and str(query).strip():
        q = str(query).strip()
        shows = [s for s in shows
                 if _fuzzy_score(q, s["title"], s.get("genre"), s.get("language"),
                                 s.get("venue_name"), s.get("city")) >= 0.6]
    if max_price is not None:
        try:
            cap = float(max_price)
            shows = [s for s in shows if s.get("current_price") is not None and s["current_price"] <= cap]
        except (TypeError, ValueError):
            logger.info("search_shows ignored a non-numeric max_price: %r", max_price)

    events = _group_by_event(shows)
    await _with_ratings(conn, events)
    if sort == "cheapest":
        events.sort(key=lambda e: (e["price_from"] is None, e["price_from"] or 0))
    elif sort == "top_rated":
        events.sort(key=lambda e: (e["avg_rating"] is None, -(e["avg_rating"] or 0)))

    return {"total_events": len(events), "events": events[:MAX_EVENTS],
            "browse_link": "/browse"}


async def _resolve_event(conn, event_id=None, title=None) -> Optional[asyncpg.Record]:
    if event_id and _is_uuid(event_id):
        row = await conn.fetchrow(
            "SELECT * FROM events WHERE id = $1::uuid AND status = 'published'", str(event_id))
        if row:
            return row
    if title and str(title).strip():
        rows = await conn.fetch("SELECT * FROM events WHERE status = 'published'")
        scored = sorted(((_fuzzy_score(str(title), r["title"]), r) for r in rows),
                        key=lambda x: -x[0])
        if scored and scored[0][0] >= 0.6:
            return scored[0][1]
    return None


NOT_FOUND = {"error": "not_found", "message": "No published event matches that. Try search_shows."}


async def get_event_details(conn, user, *, event_id=None, title=None) -> dict:
    event = await _resolve_event(conn, event_id, title)
    if not event:
        return NOT_FOUND
    eid = str(event["id"])
    shows = await _upcoming_shows(conn, event_id=eid)
    rating = await conn.fetchrow(
        """SELECT ROUND(AVG(rating)::numeric, 1) AS avg_rating, COUNT(*) AS review_count
           FROM reviews WHERE event_id = $1::uuid AND is_draft = false
             AND (scheduled_for IS NULL OR scheduled_for <= now())""",
        eid,
    )
    return {
        "event_id": eid,
        "title": event["title"],
        "type": str(event["event_type"]),
        "genre": event.get("genre"),
        "language": event.get("language"),
        "duration_minutes": event.get("duration_minutes"),
        "age_rating": event.get("age_rating") or event.get("certificate"),
        "description": _clip(event.get("description")),
        "avg_rating": float(rating["avg_rating"]) if rating and rating["avg_rating"] is not None else None,
        "review_count": int(rating["review_count"]) if rating else 0,
        "link": f"/events/{eid}",
        "reviews_link": f"/events/{eid}/reviews",
        "upcoming_shows": [
            {**_show_card(s), "address": s.get("address")} for s in shows[:10]
        ],
        "upcoming_show_count": len(shows),
    }


async def get_review_summary(conn, user, *, event_id=None, title=None) -> dict:
    event = await _resolve_event(conn, event_id, title)
    if not event:
        return NOT_FOUND
    eid = str(event["id"])
    stats = await conn.fetchrow(
        """SELECT ROUND(AVG(rating)::numeric, 1) AS avg_rating, COUNT(*) AS review_count
           FROM reviews WHERE event_id = $1::uuid AND is_draft = false
             AND (scheduled_for IS NULL OR scheduled_for <= now())""",
        eid,
    )
    cache = await conn.fetchrow(
        """SELECT overall_summary, audience_liked, audience_disliked
           FROM ai_review_summaries WHERE event_id = $1::uuid""",
        eid,
    )

    def top(value) -> list:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return []
        return [str(x) for x in (value or [])][:3]

    return {
        "title": event["title"],
        "avg_rating_out_of_10": float(stats["avg_rating"]) if stats and stats["avg_rating"] is not None else None,
        "review_count": int(stats["review_count"]) if stats else 0,
        "summary": _clip(cache["overall_summary"], 500) if cache else None,
        "people_liked": top(cache["audience_liked"]) if cache else [],
        "people_disliked": top(cache["audience_disliked"]) if cache else [],
        "reviews_link": f"/events/{eid}/reviews",
    }


async def recommend_events(conn, user, *, like_event_id=None, like_title=None, event_type=None,
                           genre=None, city=None, date_from=None, date_to=None) -> dict:
    shows = await _upcoming_shows(conn, city, event_type, _parse_date(date_from), _parse_date(date_to))
    events = _group_by_event(shows)
    await _with_ratings(conn, events)

    liked_genres: set = set(_genre_words(genre))
    liked_types: set = {event_type.lower()} if event_type else set()
    exclude: set = set()
    based_on = []

    like = await _resolve_event(conn, like_event_id, like_title) if (like_event_id or like_title) else None
    if like:
        liked_genres |= _genre_words(like.get("genre"))
        liked_types.add(str(like["event_type"]))
        exclude.add(str(like["id"]))
        based_on.append(f"similar to {like['title']}")

    if user and not like and not genre and not event_type:
        rows = await conn.fetch(
            """SELECT DISTINCT e.id, e.genre, e.event_type::text AS event_type FROM events e
               WHERE e.id IN (SELECT event_id FROM wishlists WHERE user_id = $1)
                  OR e.id IN (SELECT s.event_id FROM bookings b JOIN shows s ON s.id = b.show_id
                              WHERE b.user_id = $1 AND b.status = 'confirmed')""",
            user["id"],
        )
        for r in rows:
            liked_genres |= _genre_words(r["genre"])
            liked_types.add(r["event_type"])
        booked = await conn.fetch(
            """SELECT DISTINCT s.event_id FROM bookings b JOIN shows s ON s.id = b.show_id
               WHERE b.user_id = $1 AND b.status = 'confirmed'""",
            user["id"],
        )
        exclude |= {str(r["event_id"]) for r in booked}
        if rows:
            based_on.append("your wishlist and past bookings")

    def score(ev: dict) -> float:
        s = 2.0 * len(_genre_words(ev.get("genre")) & liked_genres)
        s += 1.0 if ev["type"] in liked_types else 0.0
        s += (ev.get("avg_rating") or 0) / 5.0
        return s

    picks = sorted((e for e in events if e["event_id"] not in exclude), key=lambda e: -score(e))
    return {"based_on": based_on or ["ratings and what is on soon"], "events": picks[:5]}


# ── the user's own data ──────────────────────────────────────────────────────

def _cancel_info(status: str, start_time: datetime) -> dict:
    cutoff = start_time - timedelta(hours=CANCEL_CUTOFF_HOURS)
    can = status == "confirmed" and datetime.now(timezone.utc) < cutoff
    return {"can_cancel_now": can, "cancel_before": _fmt_time(cutoff) if status == "confirmed" else None}


BOOKING_SQL = """
    SELECT b.id, b.booking_number, b.status::text AS status, b.total_amount, b.created_at,
           e.title AS event_title, s.start_time, v.name AS venue_name, v.city,
           (SELECT string_agg(st.row_label || st.seat_number::text, ', '
                              ORDER BY st.row_label, st.seat_number)
              FROM booking_seats bs JOIN show_seats ss ON ss.id = bs.show_seat_id
              JOIN seats st ON st.id = ss.seat_id
             WHERE bs.booking_id = b.id) AS seats,
           (SELECT p.status::text FROM payments p WHERE p.booking_id = b.id
             ORDER BY p.created_at DESC LIMIT 1) AS payment_status
    FROM bookings b
    JOIN shows s ON s.id = b.show_id
    JOIN events e ON e.id = s.event_id
    JOIN screens sc ON sc.id = s.screen_id
    JOIN venues v ON v.id = sc.venue_id
"""


def _booking_card(r: asyncpg.Record) -> dict:
    return {
        "booking_id": str(r["id"]),
        "booking_number": r["booking_number"],
        "event": r["event_title"],
        "show_time": _fmt_time(r["start_time"]),
        "venue": f"{r['venue_name']}, {r['city']}",
        "seats": r["seats"],
        "status": r["status"],
        "payment_status": r["payment_status"],
        "amount": _money(r["total_amount"]),
        "link": f"/bookings/{r['id']}",
        **_cancel_info(r["status"], r["start_time"]),
    }


async def get_my_bookings(conn, user, *, which="upcoming") -> dict:
    if not user:
        return LOGIN_REQUIRED
    where = "b.user_id = $1"
    if which == "upcoming":
        where += " AND s.start_time > now() AND b.status IN ('confirmed', 'pending')"
        order = "s.start_time ASC"
    elif which == "past":
        where += " AND s.start_time <= now()"
        order = "s.start_time DESC"
    else:
        order = "b.created_at DESC"
    rows = await conn.fetch(f"{BOOKING_SQL} WHERE {where} ORDER BY {order} LIMIT 10", user["id"])
    return {"which": which, "count": len(rows), "bookings": [_booking_card(r) for r in rows],
            "all_bookings_link": "/bookings"}


async def get_booking_status(conn, user, *, booking_id=None, booking_number=None) -> dict:
    if not user:
        return LOGIN_REQUIRED
    if booking_id and _is_uuid(booking_id):
        row = await conn.fetchrow(f"{BOOKING_SQL} WHERE b.id = $1::uuid AND b.user_id = $2",
                                  str(booking_id), user["id"])
    elif booking_number:
        row = await conn.fetchrow(f"{BOOKING_SQL} WHERE upper(b.booking_number) = upper($1) AND b.user_id = $2",
                                  str(booking_number).strip(), user["id"])
    else:
        row = None
    if not row:
        return {"error": "not_found", "message": "No booking of this user matches that."}
    return _booking_card(row)


async def get_my_wishlist(conn, user) -> dict:
    if not user:
        return LOGIN_REQUIRED
    rows = await conn.fetch(
        """SELECT e.id, e.title, e.event_type::text AS event_type,
                  (SELECT MIN(s.start_time) FROM shows s WHERE s.event_id = e.id
                     AND s.status = 'scheduled' AND s.start_time > now()) AS next_show
           FROM wishlists w JOIN events e ON e.id = w.event_id
           WHERE w.user_id = $1 ORDER BY w.created_at DESC LIMIT 20""",
        user["id"],
    )
    return {
        "count": len(rows),
        "items": [{"title": r["title"], "type": r["event_type"], "next_show": _fmt_time(r["next_show"]),
                   "link": f"/events/{r['id']}"} for r in rows],
        "wishlist_link": "/wishlist",
    }


# ── registry ─────────────────────────────────────────────────────────────────

ToolFn = Callable[..., Awaitable[dict]]

TOOLS: Dict[str, ToolFn] = {
    "search_shows": search_shows,
    "get_event_details": get_event_details,
    "get_review_summary": get_review_summary,
    "recommend_events": recommend_events,
    "get_my_bookings": get_my_bookings,
    "get_booking_status": get_booking_status,
    "get_my_wishlist": get_my_wishlist,
}


def _schema(name: str, description: str, properties: dict) -> dict:
    return {"type": "function", "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "additionalProperties": False}}


_STR = {"type": "string"}
_DATE = {"type": "string", "description": "YYYY-MM-DD (India time)"}
_TYPE = {"type": "string", "enum": list(EVENT_TYPES)}

TOOL_SCHEMAS: List[dict] = [
    _schema("search_shows",
            "Find upcoming shows. Use for any question about what is on, where, when or for how much.",
            {"query": {**_STR, "description": "Title, artist, genre or language; typos are fine"},
             "city": _STR, "event_type": _TYPE, "date_from": _DATE, "date_to": _DATE,
             "max_price": {"type": "number", "description": "Maximum ticket price in INR"},
             "sort": {"type": "string", "enum": ["soonest", "cheapest", "top_rated"]}}),
    _schema("get_event_details",
            "Details of one event: description, rating, and upcoming shows with venue, time, price and seats left.",
            {"event_id": _STR, "title": _STR}),
    _schema("get_review_summary",
            "What people think of an event: average rating (out of 10), review count and AI review summary.",
            {"event_id": _STR, "title": _STR}),
    _schema("recommend_events",
            "Suggest upcoming events. With no arguments and a logged-in user, uses their wishlist and past bookings.",
            {"like_event_id": _STR, "like_title": {**_STR, "description": "Recommend things similar to this title"},
             "event_type": _TYPE, "genre": _STR, "city": _STR, "date_from": _DATE, "date_to": _DATE}),
    _schema("get_my_bookings", "The logged-in user's own bookings.",
            {"which": {"type": "string", "enum": ["upcoming", "past", "all"]}}),
    _schema("get_booking_status",
            "Status, payment, seats and whether it can still be cancelled, for one of the user's own bookings.",
            {"booking_id": _STR, "booking_number": _STR}),
    _schema("get_my_wishlist", "Events in the logged-in user's wishlist.", {}),
]


async def run_tool(name: str, arguments: str, conn: asyncpg.Connection, user: Optional[dict]) -> dict:
    """Run one tool call from the model. Never raises; errors come back as data."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": "unknown_tool"}
    try:
        args = json.loads(arguments or "{}")
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:
        return {"error": "bad_arguments"}
    allowed = {k: v for k, v in args.items()
               if k in next(s for s in TOOL_SCHEMAS if s["name"] == name)["parameters"]["properties"]
               and v not in (None, "")}
    return await fn(conn, user, **allowed)
