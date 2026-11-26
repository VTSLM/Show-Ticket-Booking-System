"""
Personalized recommendations and trending events (#218, Registered user FR2, FR3, FR16, NFR5).

1. Candidates: published events with an upcoming scheduled show, optionally only those near
   the user's location (same rule as Browse: concerts are always listed).
2. Personal picks: every candidate is scored against the user's taste, built from confirmed
   bookings, wishlist, recently viewed events and saved preferences. Events the user
   already booked, saved or opened are left out, so every pick is new. Picks need at least one real match; a high rating alone is not enough.
3. Trending: candidates ranked by confirmed bookings in the last TRENDING_DAYS days.
4. AI reasons: an LLM writes one short line per pick. It only gets the facts listed here,
   and the whole request has RECOMMENDATIONS_TIMEOUT_SECONDS (default 3). When the model is
   slow or unavailable, the picks are returned without reasons, next to trending (NFR5).
"""
import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

import asyncpg

from routers.browse import _attach_ratings, _with_dynamic_price
from services.geo_service import DEFAULT_RADIUS_KM, venues_with_distance

logger = logging.getLogger(__name__)

MAX_PICKS = 8
MAX_TRENDING = 8
TRENDING_DAYS = 14
VIEW_DAYS = 30
MAX_PREFERENCE_ITEMS = 10
MAX_PREFERENCE_LENGTH = 40

# How much each signal counts towards a genre / type / artist the user likes
WEIGHT_BOOKED = 3.0
WEIGHT_WISHLIST = 2.0
WEIGHT_VIEWED = 1.0
WEIGHT_PREFERRED_GENRE = 3.0
WEIGHT_PREFERRED_ARTIST = 4.0
WEIGHT_PREFERRED_CITY = 1.5

REASONS_CACHE_SECONDS = 30 * 60
_REASONS_CACHE_MAX = 500
_reasons_cache: Dict[tuple, tuple] = {}


def timeout_seconds() -> float:
    try:
        return max(0.5, float(os.getenv("RECOMMENDATIONS_TIMEOUT_SECONDS", "3")))
    except ValueError:
        return 3.0


def ai_enabled() -> bool:
    return (os.getenv("RECOMMENDATIONS_AI", "true").strip().lower()
            not in ("0", "false", "no", "off"))


# ── small helpers ────────────────────────────────────────────────────────────

def words(text: Optional[str]) -> set:
    """Lower-case words of a genre string: 'Sci-Fi / Thriller' -> {'sci', 'fi', 'thriller'}."""
    return {w for w in re.split(r"[^a-z]+", (text or "").lower()) if len(w) > 1}


def artist_names(value: Any) -> List[str]:
    """Names from the events.artists / cast_crew JSON: [{"name": ..., "role": ...}] or ["name"]."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    names = []
    for item in value or []:
        name = item.get("name") if isinstance(item, dict) else item
        if isinstance(name, str) and name.strip():
            names.append(" ".join(name.split()))
    return names


def clean_list(values: Optional[Iterable[str]]) -> List[str]:
    """Trim, drop empties and case-insensitive duplicates, cap the count and length."""
    out, seen = [], set()
    for v in values or []:
        if not isinstance(v, str):
            continue
        v = " ".join(v.split())[:MAX_PREFERENCE_LENGTH]
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
        if len(out) >= MAX_PREFERENCE_ITEMS:
            break
    return out


# ── preferences and views ────────────────────────────────────────────────────

async def get_preferences(conn: asyncpg.Connection, user_id) -> dict:
    row = await conn.fetchrow(
        "SELECT genres, artists, cities, updated_at FROM user_preferences WHERE user_id = $1",
        user_id,
    )
    if not row:
        return {"genres": [], "artists": [], "cities": [], "updated_at": None}
    return {
        "genres": list(row["genres"] or []),
        "artists": list(row["artists"] or []),
        "cities": list(row["cities"] or []),
        "updated_at": row["updated_at"],
    }


async def save_preferences(conn: asyncpg.Connection, user_id, genres, artists, cities) -> dict:
    await conn.execute(
        """INSERT INTO user_preferences (user_id, genres, artists, cities, updated_at)
           VALUES ($1, $2::text[], $3::text[], $4::text[], now())
           ON CONFLICT (user_id) DO UPDATE
              SET genres = EXCLUDED.genres, artists = EXCLUDED.artists,
                  cities = EXCLUDED.cities, updated_at = now()""",
        user_id, clean_list(genres), clean_list(artists), clean_list(cities),
    )
    return await get_preferences(conn, user_id)


async def record_view(conn: asyncpg.Connection, user_id, event_id: str) -> bool:
    """Count one view of a published event. Returns False when the event is not published."""
    status = await conn.execute(
        """INSERT INTO event_views (user_id, event_id)
           SELECT $1, e.id FROM events e WHERE e.id = $2::uuid AND e.status = 'published'
           ON CONFLICT (user_id, event_id) DO UPDATE
              SET view_count = event_views.view_count + 1, last_viewed_at = now()""",
        user_id, event_id,
    )
    return not str(status).endswith(" 0")


async def preference_options(conn: asyncpg.Connection) -> dict:
    """Suggestions for the preference pickers, taken from published events and venues."""
    rows = await conn.fetch(
        "SELECT genre, artists, cast_crew FROM events WHERE status = 'published'")
    genres: Dict[str, str] = {}
    artist_count: Dict[str, int] = defaultdict(int)
    for r in rows:
        for part in re.split(r"[,/|]", r["genre"] or ""):
            part = " ".join(part.split())
            if part:
                genres.setdefault(part.lower(), part.title())
        for name in artist_names(r["artists"]) + artist_names(r["cast_crew"]):
            artist_count[name] += 1
    cities = await conn.fetch(
        "SELECT DISTINCT city FROM venues WHERE city IS NOT NULL AND city <> '' ORDER BY city")
    return {
        "genres": sorted(genres.values()),
        "artists": [n for n, _ in sorted(artist_count.items(), key=lambda x: (-x[1], x[0]))][:60],
        "cities": [r["city"] for r in cities],
    }


# ── candidates ───────────────────────────────────────────────────────────────

SHOWS_PER_EVENT = 15

# The next SHOWS_PER_EVENT shows of every published event ($1: venue ids near the user, or
# NULL for everywhere; concerts are always listed, same rule as Browse). Seat counts are only
# worked out for those shows.
CANDIDATES_SQL = """
    WITH upcoming AS (
        SELECT s.id, s.start_time, s.dynamic_pricing, s.event_id, v.id AS venue_id,
               ROW_NUMBER() OVER (PARTITION BY s.event_id ORDER BY s.start_time) AS n
        FROM shows s
        JOIN events e ON e.id = s.event_id
        JOIN screens sc ON sc.id = s.screen_id
        JOIN venues v ON v.id = sc.venue_id
        WHERE s.status = 'scheduled' AND e.status = 'published' AND s.start_time > now()
          AND ($1::uuid[] IS NULL OR e.event_type::text = 'concert' OR v.id = ANY($1::uuid[]))
    )
    SELECT u.id AS show_id, u.start_time, u.dynamic_pricing,
           e.id AS event_id, e.title, e.event_type::text AS event_type, e.language, e.genre,
           e.poster_url, e.artists, e.cast_crew,
           v.id AS venue_id, v.name AS venue_name, v.city,
           seats.base_price, seats.available_seats, seats.sold_seats, seats.total_seats
    FROM upcoming u
    JOIN events e ON e.id = u.event_id
    JOIN venues v ON v.id = u.venue_id
    LEFT JOIN LATERAL (
        SELECT MIN(ss.price) AS base_price,
               COUNT(*) FILTER (WHERE ss.status = 'available') AS available_seats,
               COUNT(*) FILTER (WHERE ss.status = 'booked') AS sold_seats,
               COUNT(*) AS total_seats
        FROM show_seats ss WHERE ss.show_id = u.id
    ) seats ON true
    WHERE u.n <= SHOWS_PER_EVENT
    ORDER BY u.start_time
""".replace("SHOWS_PER_EVENT", str(SHOWS_PER_EVENT))


async def nearby_venue_ids(conn: asyncpg.Connection, lat: float, lng: float,
                           radius_km: float) -> List[str]:
    rows = await conn.fetch("SELECT id, city, latitude, longitude FROM venues")
    return [str(d["venue_id"]) for d in venues_with_distance([dict(r) for r in rows], lat, lng)
            if d["distance_km"] <= radius_km]


def _group(shows: List[dict]) -> List[dict]:
    """One card per event: next show, its city, the lowest current price, all cities."""
    events: Dict[str, dict] = {}
    for s in shows:
        key = str(s["event_id"])
        ev = events.get(key)
        if ev is None:
            ev = events[key] = {
                "event_id": key,
                "title": s["title"],
                "event_type": s["event_type"],
                "genre": s.get("genre"),
                "language": s.get("language"),
                "poster_url": s.get("poster_url"),
                "artists": artist_names(s.get("artists")) + artist_names(s.get("cast_crew")),
                "next_show_time": s["start_time"],
                "city": s.get("city"),
                "cities": set(),
                "price_from": None,
                "show_count": 0,
                "link": f"/events/{key}",
            }
        ev["show_count"] += 1
        if s.get("city"):
            ev["cities"].add(s["city"])
        price = s.get("current_price")
        if price is not None and (ev["price_from"] is None or price < ev["price_from"]):
            ev["price_from"] = round(float(price), 2)
    return list(events.values())


async def load_candidates(conn: asyncpg.Connection, lat: Optional[float] = None,
                          lng: Optional[float] = None,
                          radius_km: float = DEFAULT_RADIUS_KM) -> List[dict]:
    near = None if lat is None or lng is None else await nearby_venue_ids(conn, lat, lng, radius_km)
    rows = await conn.fetch(CANDIDATES_SQL, near)
    shows = [_with_dynamic_price(dict(r)) for r in rows]
    events = _group(shows)
    await _attach_ratings(conn, events)
    return events


# ── trending ─────────────────────────────────────────────────────────────────

async def trending(conn: asyncpg.Connection, candidates: List[dict],
                   limit: int = MAX_TRENDING) -> List[dict]:
    """Most booked in the last TRENDING_DAYS days; ties go to the better rated, then the sooner."""
    if not candidates:
        return []
    rows = await conn.fetch(
        """SELECT s.event_id, COUNT(DISTINCT b.id) AS bookings
           FROM bookings b JOIN shows s ON s.id = b.show_id
           WHERE b.status = 'confirmed' AND b.created_at > now() - make_interval(days => $2)
             AND s.event_id = ANY($1::uuid[])
           GROUP BY s.event_id""",
        [c["event_id"] for c in candidates], TRENDING_DAYS,
    )
    counts = {str(r["event_id"]): int(r["bookings"]) for r in rows}
    ranked = sorted(
        candidates,
        key=lambda c: (-counts.get(c["event_id"], 0), -(c.get("avg_rating") or 0),
                       c["next_show_time"]),
    )
    return [{**c, "recent_bookings": counts.get(c["event_id"], 0)} for c in ranked[:limit]]


# ── the user's taste ─────────────────────────────────────────────────────────

TASTE_SQL = """
    SELECT e.id, e.title, e.genre, e.event_type::text AS event_type, e.artists, e.cast_crew,
           'booked' AS source, 1 AS times
      FROM bookings b JOIN shows s ON s.id = b.show_id JOIN events e ON e.id = s.event_id
     WHERE b.user_id = $1 AND b.status = 'confirmed'
    UNION ALL
    SELECT e.id, e.title, e.genre, e.event_type::text, e.artists, e.cast_crew, 'wishlist', 1
      FROM wishlists w JOIN events e ON e.id = w.event_id
     WHERE w.user_id = $1
    UNION ALL
    SELECT e.id, e.title, e.genre, e.event_type::text, e.artists, e.cast_crew, 'viewed',
           LEAST(v.view_count, 3)
      FROM event_views v JOIN events e ON e.id = v.event_id
     WHERE v.user_id = $1 AND v.last_viewed_at > now() - make_interval(days => $2)
"""

SOURCE_WEIGHT = {"booked": WEIGHT_BOOKED, "wishlist": WEIGHT_WISHLIST, "viewed": WEIGHT_VIEWED}


async def load_taste(conn: asyncpg.Connection, user_id) -> dict:
    prefs = await get_preferences(conn, user_id)
    rows = await conn.fetch(TASTE_SQL, user_id, VIEW_DAYS)

    genres: Dict[str, float] = defaultdict(float)
    types: Dict[str, float] = defaultdict(float)
    artists: Dict[str, float] = defaultdict(float)
    anchors: Dict[str, dict] = {}      # event id -> {"title", "source", "genre_words", "artists"}
    booked: set = set()
    sources: set = set()

    for r in rows:
        source = r["source"]
        weight = SOURCE_WEIGHT[source]
        if source == "viewed":            # opening a page again counts a little more, max 2x
            weight *= 1 + 0.5 * (min(int(r["times"] or 1), 3) - 1)
        names = artist_names(r["artists"]) + artist_names(r["cast_crew"])
        for w in words(r["genre"]):
            genres[w] += weight
        types[str(r["event_type"]).lower()] += weight
        for n in names:
            artists[n.lower()] += weight / 2
        key = str(r["id"])
        sources.add(source)
        if source == "booked":
            booked.add(key)
        current = anchors.get(key)
        if current is None or SOURCE_WEIGHT[source] > SOURCE_WEIGHT[current["source"]]:
            anchors[key] = {"title": r["title"], "source": source,
                            "genre_words": words(r["genre"]), "artists": {n.lower() for n in names}}

    for g in prefs["genres"]:
        for w in words(g):
            genres[w] += WEIGHT_PREFERRED_GENRE
    for a in prefs["artists"]:
        artists[a.lower()] += WEIGHT_PREFERRED_ARTIST

    if any(prefs[k] for k in ("genres", "artists", "cities")):
        sources.add("preferences")

    return {
        "genres": dict(genres), "types": dict(types), "artists": dict(artists),
        "preferred_genres": prefs["genres"], "preferred_artists": prefs["artists"],
        "preferred_cities": {c.lower() for c in prefs["cities"]},
        "anchors": anchors, "booked": booked, "sources": sources,
    }


def has_taste(taste: dict) -> bool:
    return bool(taste["genres"] or taste["artists"] or taste["types"] or taste["preferred_cities"])


# ── scoring ──────────────────────────────────────────────────────────────────

def _because(event: dict, taste: dict) -> Optional[str]:
    """The strongest past event this one resembles, for a 'Because you booked X' label."""
    ev_words = words(event.get("genre"))
    ev_artists = {a.lower() for a in event.get("artists", [])}
    best, best_score = None, 0.0
    for key, a in taste["anchors"].items():
        if key == event["event_id"]:
            continue
        s = 2 * len(a["artists"] & ev_artists) + len(a["genre_words"] & ev_words)
        s *= SOURCE_WEIGHT[a["source"]]
        if s > best_score:
            best, best_score = a, s
    if not best:
        return None
    verb = {"booked": "booked", "wishlist": "saved", "viewed": "looked at"}[best["source"]]
    return f"Because you {verb} {best['title']}"


def score_event(event: dict, taste: dict) -> tuple:
    """(score, match labels). Score 0 means nothing about the event matches the user."""
    labels: List[str] = []
    score = 0.0

    ev_words = words(event.get("genre"))
    genre_hits = [w for w in ev_words if w in taste["genres"]]
    score += sum(taste["genres"][w] for w in genre_hits)
    preferred = [g for g in taste["preferred_genres"] if words(g) & ev_words]
    if preferred:
        labels.append(f"You like {preferred[0]}")

    for name in event.get("artists", []):
        if name.lower() in taste["artists"]:
            score += 2 * taste["artists"][name.lower()]
            labels.append(f"Features {name}")
            break

    # the type only counts next to a genre or artist match, else every movie would match
    if score > 0:
        score += 0.5 * taste["types"].get(str(event["event_type"]).lower(), 0)

    if taste["preferred_cities"]:
        city = next((c for c in event.get("cities", set())
                     if c.lower() in taste["preferred_cities"]), None)
        if city:
            score += WEIGHT_PREFERRED_CITY
            labels.append(f"In {city}")

    if score <= 0:
        return 0.0, []

    because = _because(event, taste)
    if because:
        labels.insert(0, because)
    score += (event.get("avg_rating") or 0) / 10.0      # ratings are out of 10
    return score, labels[:2]


def personal_picks(candidates: List[dict], taste: dict, limit: int = MAX_PICKS) -> List[dict]:
    """New events only: anything the user booked, saved or opened is left out."""
    seen = set(taste["anchors"]) | taste["booked"]
    scored = []
    for ev in candidates:
        if ev["event_id"] in seen:
            continue
        s, labels = score_event(ev, taste)
        if s > 0:
            scored.append((s, ev, labels))
    scored.sort(key=lambda x: (-x[0], x[1]["next_show_time"]))
    picks = []
    for s, ev, labels in scored[:limit]:
        # show the preferred city on the card when the event plays there
        city = next((c for c in sorted(ev.get("cities", ()))
                     if c.lower() in taste["preferred_cities"]), ev.get("city"))
        picks.append({**ev, "city": city, "match": labels, "score": round(s, 2)})
    return picks


# ── AI reasons ───────────────────────────────────────────────────────────────

REASONS_PROMPT = """You write the one-line reason shown under each recommended event on TicketFlow,
an Indian ticket booking site. Use ONLY the facts given. Never invent plot, cast, awards,
reviews, prices or dates. Do not use the user's name. Each reason: one sentence, at most
18 words, friendly, no emojis, no quotation marks. Return ONLY JSON:
{"reasons": {"<event_id>": "<reason>", ...}} with one entry per event."""


def _taste_summary(taste: dict) -> dict:
    top = lambda d: [k for k, _ in sorted(d.items(), key=lambda x: -x[1])[:5]]  # noqa: E731
    return {
        "likes_genres": taste["preferred_genres"] or top(taste["genres"]),
        "likes_artists": taste["preferred_artists"] or top(taste["artists"]),
        "recent_events": [
            {"title": a["title"], "how": a["source"]}
            for a in list(taste["anchors"].values())[:6]
        ],
    }


def _parse_reasons(text: str, ids: set) -> Dict[str, str]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return {}
    reasons = data.get("reasons", data) if isinstance(data, dict) else {}
    out = {}
    for k, v in (reasons or {}).items():
        if str(k) in ids and isinstance(v, str) and v.strip():
            out[str(k)] = " ".join(v.split())[:160]
    return out


async def _ask_model(picks: List[dict], taste: dict) -> Dict[str, str]:
    from services import chatbot     # same model service and keys as the assistant

    client = chatbot._get_client()   # raises AssistantUnavailable when no key is set
    payload = {
        "user": _taste_summary(taste),
        "events": [
            {"event_id": p["event_id"], "title": p["title"], "type": p["event_type"],
             "genre": p.get("genre"), "language": p.get("language"),
             "artists": p.get("artists", [])[:3], "matches": p.get("match", []),
             "avg_rating_out_of_10": p.get("avg_rating")}
            for p in picks
        ],
    }
    extra = {}
    effort = chatbot._reasoning_effort(chatbot._provider())
    if effort:
        extra["reasoning_effort"] = effort
    response = await client.chat.completions.create(
        model=chatbot._model(),
        messages=[{"role": "system", "content": REASONS_PROMPT},
                  {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
        **extra,
    )
    text = response.choices[0].message.content or ""
    return _parse_reasons(text, {p["event_id"] for p in picks})


def _cache_get(key: tuple) -> Optional[Dict[str, str]]:
    hit = _reasons_cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    _reasons_cache.pop(key, None)
    return None


def _cache_put(key: tuple, reasons: Dict[str, str]) -> None:
    if len(_reasons_cache) >= _REASONS_CACHE_MAX:
        _reasons_cache.pop(next(iter(_reasons_cache)))
    _reasons_cache[key] = (time.monotonic() + REASONS_CACHE_SECONDS, reasons)


async def ai_reasons(user_id, picks: List[dict], taste: dict, budget: float) -> tuple:
    """(reasons by event id, None) or ({}, 'ai_timeout' | 'ai_unavailable' | 'ai_off')."""
    if not picks:
        return {}, None
    if not ai_enabled():
        return {}, "ai_off"
    key = (str(user_id), tuple(p["event_id"] for p in picks))
    cached = _cache_get(key)
    if cached is not None:
        return cached, None
    if budget <= 0.2:
        return {}, "ai_timeout"
    try:
        reasons = await asyncio.wait_for(_ask_model(picks, taste), timeout=budget)
    except asyncio.TimeoutError:
        logger.info("Recommendation reasons took over %.1fs; returning picks without them", budget)
        return {}, "ai_timeout"
    except Exception as exc:      # missing key, quota, network, bad output
        logger.warning("Recommendation reasons unavailable: %s", exc)
        return {}, "ai_unavailable"
    if not reasons:
        return {}, "ai_unavailable"
    _cache_put(key, reasons)
    return reasons, None


# ── response ─────────────────────────────────────────────────────────────────

def card(event: dict) -> dict:
    """The JSON the home page needs for one event."""
    t = event.get("next_show_time")
    return {
        "event_id": event["event_id"],
        "title": event["title"],
        "event_type": event["event_type"],
        "genre": event.get("genre"),
        "language": event.get("language"),
        "poster_url": event.get("poster_url"),
        "next_show_time": t.isoformat() if hasattr(t, "isoformat") else t,
        "city": event.get("city"),
        "price_from": event.get("price_from"),
        "avg_rating": event.get("avg_rating"),
        "review_count": event.get("review_count") or 0,
        "link": event["link"],
        **({"match": event["match"]} if "match" in event else {}),
        **({"reason": event.get("reason")} if "match" in event else {}),
        **({"recent_bookings": event["recent_bookings"]} if "recent_bookings" in event else {}),
    }


async def build(conn: asyncpg.Connection, user: Optional[dict], lat: Optional[float] = None,
                lng: Optional[float] = None, radius_km: float = DEFAULT_RADIUS_KM) -> dict:
    started = time.monotonic()
    candidates = await load_candidates(conn, lat, lng, radius_km)
    trend = await trending(conn, candidates)

    result = {
        "personalized": False,
        "recommended": [],
        "trending": [card(t) for t in trend],
        "ai_reasons": False,
        "fallback": None,
        "based_on": [],
    }
    if not user:
        result["fallback"] = "guest"
        return result

    taste = await load_taste(conn, user["id"])
    picks = personal_picks(candidates, taste) if has_taste(taste) else []
    if not picks:
        result["fallback"] = "no_history"
        return result

    budget = timeout_seconds() - (time.monotonic() - started)
    reasons, fallback = await ai_reasons(user["id"], picks, taste, budget)
    for p in picks:
        p["reason"] = reasons.get(p["event_id"])

    order = ["booked", "wishlist", "viewed", "preferences"]
    labels = {"booked": "your bookings", "wishlist": "your wishlist",
              "viewed": "events you viewed", "preferences": "your preferences"}
    result.update(
        personalized=True,
        recommended=[card(p) for p in picks],
        ai_reasons=bool(reasons),
        fallback=fallback,
        based_on=[labels[s] for s in order if s in taste["sources"]],
    )
    return result
