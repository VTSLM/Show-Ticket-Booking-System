"""
TicketFlow — Critics Reviews & Ratings Router (Sprint 2 Module)
Matches TicketFlow variables: events, shows, users, asyncpg, and UUIDs.
"""
import json
import logging
import os
import uuid as uuid_module
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user
from firebase_admin_setup import verify_firebase_token
from services.ai_review_summary_service import generate_summary
from schemas.reviews import (
    CreateReviewRequest,
    UpdateReviewRequest,
    ReviewOut,
    ReviewAuthor,
    CommentOut,
    CommentCreate,
    ReviewVersionOut,
    MovieAggregatesOut,
    EventReviewsResponse,
    CriticProfileOut,
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
logger = logging.getLogger("uvicorn.error")
optional_security = HTTPBearer(auto_error=False)

CRITIC_MIN_WORDS = int(os.getenv("CRITIC_MIN_WORDS", "10"))
CRITIC_MAX_WORDS = int(os.getenv("CRITIC_MAX_WORDS", "1000"))


def is_approved_critic(user: Optional[dict]) -> bool:
    if not user:
        return False
    roles = user.get("roles") or []
    return "critic" in roles or "admin" in roles


def count_words(content: str, sections: Optional[dict] = None) -> int:
    words = len(content.split())
    if sections and isinstance(sections, dict):
        for val in sections.values():
            if isinstance(val, str):
                words += len(val.split())
    return words

# A review is PUBLIC once it is not a draft and its scheduled time (if any) has passed.
# No cron job needed: reviews whose time has not come are simply filtered out.
# "r" must be the alias of the reviews table in any query that uses this fragment.
PUBLIC_REVIEW_SQL = "(r.is_draft = false AND (r.scheduled_for IS NULL OR r.scheduled_for <= now()))"

# "Verified attendee": the reviewer holds a ticket (not cancelled) for a show of this event.
# "r" must be the alias of the reviews table.
VERIFIED_ATTENDEE_SQL = """(
    EXISTS (
        SELECT 1 FROM tickets t
        JOIN shows s ON s.id = t.show_id
        WHERE t.user_id = r.user_id AND s.event_id = r.event_id AND t.status IN ('valid', 'used')
    )
    OR EXISTS (
        SELECT 1 FROM bookings b
        JOIN shows s2 ON s2.id = b.show_id
        WHERE b.user_id = r.user_id AND s2.event_id = r.event_id
          AND b.status::text IN ('confirmed', 'completed')
    )
)"""

REPORT_REASONS = ("spam", "abusive", "spoiler", "off_topic", "other")

MIN_SCHEDULE_LEAD = timedelta(minutes=1)
MAX_SCHEDULE_AHEAD = timedelta(days=365)


def validate_schedule(when: datetime) -> datetime:
    """Return `when` as an aware UTC datetime, or raise 400 if it is not a sensible future time."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if when < now + MIN_SCHEDULE_LEAD:
        raise HTTPException(status_code=400, detail="Scheduled time must be at least 1 minute in the future")
    if when > now + MAX_SCHEDULE_AHEAD:
        raise HTTPException(status_code=400, detail="Reviews can be scheduled at most 1 year ahead")
    return when


async def get_optional_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    conn: asyncpg.Connection = Depends(get_conn)
) -> Optional[dict]:
    """Graceful auth dependency allowing anonymous reads or authenticated writes."""
    if not auth or not auth.credentials:
        return None
    try:
        decoded = verify_firebase_token(auth.credentials)
        uid = decoded["uid"]
        row = await conn.fetchrow(
            """
            SELECT u.id, u.firebase_uid, u.name, u.email, u.phone, u.status,
                   u.is_verified, u.publication, u.avatar_url, u.bio,
                   array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles r ON r.id = ur.role_id
            WHERE u.firebase_uid = $1
            GROUP BY u.id
            """,
            uid
        )
        if not row or row["status"] != "active":
            return None  # unknown, pending or blocked accounts are treated as anonymous
        user = dict(row)
        user["roles"] = list(user["roles"]) if user["roles"] else []
        return user
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /api/reviews/events/{event_id} — Dual Review List & Aggregates (FR-07, FR-21, FR-22)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/events/{event_id}", response_model=EventReviewsResponse)
async def get_event_reviews(
    event_id: uuid_module.UUID,
    critic_only: Optional[bool] = Query(None, description="Filter verified critic reviews only (FR-21)"),
    audience_only: Optional[bool] = Query(None, description="Filter audience reviews only (FR-21)"),
    sort_by: str = Query("newest", pattern="^(newest|highest|lowest|helpful)$"),
    current_user: Optional[dict] = Depends(get_optional_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    # Verify event exists
    event = await conn.fetchrow("SELECT id, title FROM events WHERE id=$1", event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # A. Calculate Live Aggregations (FR-07, NFR-17)
    all_reviews_rows = await conn.fetch(
        f"""
        SELECT r.rating, u.is_verified, array_agg(ro.code) as roles
        FROM reviews r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles ro ON ro.id = ur.role_id
        WHERE r.event_id = $1 AND {PUBLIC_REVIEW_SQL}
        GROUP BY r.id, r.rating, u.is_verified
        """,
        event_id
    )

    critic_scores = []
    user_scores = []
    for row in all_reviews_rows:
        roles = row["roles"] or []
        is_critic = ("critic" in roles) or ("admin" in roles)
        rating_val = float(row["rating"])
        if is_critic:
            critic_scores.append(rating_val)
        else:
            user_scores.append(rating_val)

    # Critic aggregations
    tot_critics = len(critic_scores)
    avg_critic = round(sum(critic_scores) / tot_critics, 1) if tot_critics > 0 else 0.0
    fresh_critics = sum(1 for s in critic_scores if s >= 6.0)
    critic_fresh_pct = int(round((fresh_critics / tot_critics) * 100)) if tot_critics > 0 else 0

    # User aggregations
    tot_users = len(user_scores)
    avg_user = round(sum(user_scores) / tot_users, 1) if tot_users > 0 else 0.0
    fresh_users = sum(1 for s in user_scores if s >= 6.0)
    user_fresh_pct = int(round((fresh_users / tot_users) * 100)) if tot_users > 0 else 0

    aggregates = MovieAggregatesOut(
        average_critic_score=avg_critic,
        critic_fresh_percentage=critic_fresh_pct,
        total_critic_reviews=tot_critics,
        average_user_score=avg_user,
        user_fresh_percentage=user_fresh_pct,
        total_user_reviews=tot_users
    )

    # B. Fetch Reviews with Author, Upvotes & Comments
    filters = ["r.event_id = $1", PUBLIC_REVIEW_SQL]
    params = [event_id]
    if critic_only is True:
        filters.append(
            "(EXISTS ("
            "SELECT 1 FROM user_roles urc JOIN roles rc ON rc.id = urc.role_id "
            "WHERE urc.user_id = r.user_id AND rc.code IN ('critic', 'admin')))"
        )
    elif audience_only is True:
        filters.append(
            "(NOT EXISTS ("
            "SELECT 1 FROM user_roles ura JOIN roles ra ON ra.id = ura.role_id "
            "WHERE ura.user_id = r.user_id AND ra.code IN ('critic', 'admin')))"
        )

    where_clause = " AND ".join(filters)

    order_by_sql = "r.published_at DESC"
    if sort_by == "highest":
        order_by_sql = "r.rating DESC, r.published_at DESC"
    elif sort_by == "lowest":
        order_by_sql = "r.rating ASC, r.published_at DESC"
    elif sort_by == "helpful":
        order_by_sql = "upvotes_count DESC, r.published_at DESC"

    # Query with aggregated counts
    sql = f"""
    SELECT r.id, r.event_id, r.user_id, r.rating, r.headline, r.content,
           r.sections_json, r.media_url, r.is_spoiler, r.is_draft, r.version,
           r.published_at, r.updated_at,
           u.name as author_name, u.email as author_email, u.is_verified as author_verified,
           u.publication as author_publication, u.avatar_url as author_avatar, u.bio as author_bio,
           {VERIFIED_ATTENDEE_SQL} AS is_verified_attendee,
           w.watched_at, w.watched_venue, w.watched_city,
           array_agg(DISTINCT ro.code) FILTER (WHERE ro.code IS NOT NULL) as author_roles,
           COUNT(DISTINCT up.user_id) as upvotes_count,
           COUNT(DISTINCT rv.id) as versions_count
    FROM reviews r
    JOIN users u ON u.id = r.user_id
    LEFT JOIN LATERAL (
        SELECT s.start_time AS watched_at, v.name AS watched_venue, v.city AS watched_city
        FROM bookings b
        JOIN shows s    ON s.id  = b.show_id
        JOIN screens sc ON sc.id = s.screen_id
        JOIN venues v   ON v.id  = sc.venue_id
        WHERE b.user_id = r.user_id AND s.event_id = r.event_id
          AND b.status::text IN ('confirmed', 'completed')
        ORDER BY s.start_time DESC
        LIMIT 1
    ) w ON true
    LEFT JOIN user_roles ur ON ur.user_id = u.id
    LEFT JOIN roles ro ON ro.id = ur.role_id
    LEFT JOIN review_upvotes up ON up.review_id = r.id
    LEFT JOIN review_versions rv ON rv.review_id = r.id
    WHERE {where_clause}
    GROUP BY r.id, u.id, w.watched_at, w.watched_venue, w.watched_city
    ORDER BY {order_by_sql}
    """

    reviews_rows = await conn.fetch(sql, *params)

    # Fetch upvotes by current user if logged in
    current_user_id = current_user["id"] if current_user else None
    upvoted_set = set()
    if current_user_id:
        upvoted_rows = await conn.fetch(
            "SELECT review_id FROM review_upvotes WHERE user_id=$1",
            current_user_id
        )
        upvoted_set = {str(r["review_id"]) for r in upvoted_rows}

    # Reviews the current user has already reported (so the UI can show "Reported")
    reported_set = set()
    if current_user_id:
        reported_rows = await conn.fetch(
            "SELECT review_id FROM review_reports WHERE reporter_id=$1",
            current_user_id
        )
        reported_set = {str(r["review_id"]) for r in reported_rows}

    # Fetch comments for these reviews
    review_ids = [r["id"] for r in reviews_rows]
    comments_by_review: Dict[str, List[CommentOut]] = {str(rid): [] for rid in review_ids}
    author_by_review = {str(r["id"]): r["user_id"] for r in reviews_rows}
    if review_ids:
        comment_rows = await conn.fetch(
            """
            SELECT c.id, c.review_id, c.user_id, c.parent_comment_id, c.content, c.is_pinned, c.created_at,
                   u.name as author_name, u.avatar_url as author_avatar, u.is_verified,
                   array_agg(ro.code) as roles
            FROM review_comments c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles ro ON ro.id = ur.role_id
            WHERE c.review_id = ANY($1)
            GROUP BY c.id, u.id
            ORDER BY c.is_pinned DESC, c.created_at ASC
            """,
            review_ids
        )
        for crow in comment_rows:
            croles = crow["roles"] or []
            is_c_critic = ("critic" in croles) or ("admin" in croles)
            cmt = CommentOut(
                id=str(crow["id"]),
                review_id=str(crow["review_id"]),
                user_id=str(crow["user_id"]),
                content=crow["content"],
                is_pinned=crow["is_pinned"],
                created_at=crow["created_at"],
                author_name=crow["author_name"],
                author_avatar=crow["author_avatar"],
                is_critic=is_c_critic,
                parent_comment_id=str(crow["parent_comment_id"]) if crow["parent_comment_id"] else None,
                is_review_author=crow["user_id"] == author_by_review.get(str(crow["review_id"]))
            )
            comments_by_review[str(crow["review_id"])].append(cmt)

    reviews_out = []
    for r in reviews_rows:
        rid_str = str(r["id"])
        roles = r["author_roles"] or []
        primary_role = "critic" if ("critic" in roles or "admin" in roles) else "customer"

        # Parse sections json
        sections_dict = None
        if r["sections_json"]:
            try:
                sections_dict = json.loads(r["sections_json"]) if isinstance(r["sections_json"], str) else r["sections_json"]
            except Exception:
                sections_dict = None

        author = ReviewAuthor(
            id=str(r["user_id"]),
            name=r["author_name"],
            email=r["author_email"],
            role=primary_role,
            is_verified=bool(r["author_verified"]),
            publication=r["author_publication"],
            avatar_url=r["author_avatar"],
            bio=r["author_bio"]
        )

        review_item = ReviewOut(
            id=rid_str,
            event_id=str(r["event_id"]),
            user_id=str(r["user_id"]),
            rating=float(r["rating"]),
            headline=r["headline"],
            content=r["content"],
            sections=sections_dict,
            media_url=r["media_url"],
            is_spoiler=r["is_spoiler"],
            is_draft=r["is_draft"],
            version=r["version"],
            published_at=r["published_at"],
            updated_at=r["updated_at"],
            author=author,
            upvotes_count=r["upvotes_count"],
            has_upvoted=rid_str in upvoted_set,
            has_reported=rid_str in reported_set,
            is_verified_attendee=bool(r["is_verified_attendee"]),
            watched_at=r["watched_at"],
            watched_venue=r["watched_venue"],
            watched_city=r["watched_city"],
            comments_count=len(comments_by_review.get(rid_str, [])),
            comments=comments_by_review.get(rid_str, []),
            versions_count=r["versions_count"]
        )
        reviews_out.append(review_item)

    return EventReviewsResponse(
        event_id=str(event_id),
        aggregates=aggregates,
        reviews=reviews_out
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1b. GET /api/reviews/events/{event_id}/mine — the logged-in user's own review
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/events/{event_id}/mine")
async def get_my_review(
    event_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        """
        SELECT id, rating, headline, content, is_spoiler, is_draft, version, scheduled_for,
               (is_draft = false AND scheduled_for IS NOT NULL AND scheduled_for > now()) AS is_scheduled
        FROM reviews WHERE event_id=$1 AND user_id=$2
        """,
        event_id, current_user["id"]
    )
    if not row:
        return {"review": None}
    return {"review": {
        "id": str(row["id"]),
        "rating": float(row["rating"]),
        "headline": row["headline"],
        "content": row["content"],
        "is_spoiler": row["is_spoiler"],
        "is_draft": row["is_draft"],
        "version": row["version"],
        "scheduled_for": row["scheduled_for"].isoformat() if row["scheduled_for"] else None,
        "is_scheduled": bool(row["is_scheduled"]),
    }}


@router.get("/events/{event_id}/ai-summary")
async def get_ai_review_summary(
    event_id: uuid_module.UUID,
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Return a cached AI summary, regenerating it when reviews changed or cache expired."""
    event = await conn.fetchrow("SELECT id, title FROM events WHERE id=$1", event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    source = await conn.fetchrow(
        f"""
        SELECT COUNT(*) AS review_count, MAX(r.updated_at) AS source_review_updated_at
        FROM reviews r
        WHERE r.event_id=$1 AND {PUBLIC_REVIEW_SQL}
        """,
        event_id,
    )
    review_count = int(source["review_count"] or 0)
    source_updated_at = source["source_review_updated_at"]

    cache = await conn.fetchrow(
        "SELECT * FROM ai_review_summaries WHERE event_id=$1",
        event_id,
    )

    cache_days = int(os.getenv("AI_REVIEW_CACHE_DAYS", "7"))
    cache_valid = False
    if cache:
        generated_at = cache["generated_at"]
        age = datetime.now(timezone.utc) - generated_at
        same_source = (
            int(cache["review_count"]) == review_count
            and cache["source_review_updated_at"] == source_updated_at
        )
        cache_valid = same_source and age <= timedelta(days=cache_days)

    if cache_valid:
        return {
            "event_id": str(event_id),
            "cached": True,
            "generated_at": cache["generated_at"].isoformat(),
            "review_count": review_count,
            "audience_rating": float(cache["audience_rating"]),
            "critic_rating": float(cache["critic_rating"]),
            "overall_rating": float(cache["overall_rating"]),
            "audience_summary": cache["audience_summary"],
            "critic_summary": cache["critic_summary"],
            "overall_summary": cache["overall_summary"],
            "audience_liked": cache["audience_liked"] or [],
            "audience_disliked": cache["audience_disliked"] or [],
            "critic_liked": cache["critic_liked"] or [],
            "critic_disliked": cache["critic_disliked"] or [],
        }

    # Match the existing review-router definition of critic vs audience.
    rows = await conn.fetch(
        f"""
        SELECT r.rating, r.headline, r.content, r.is_spoiler,
               CASE
                 WHEN EXISTS (
                   SELECT 1 FROM user_roles ur
                   JOIN roles ro ON ro.id=ur.role_id
                   WHERE ur.user_id=r.user_id AND ro.code IN ('critic','admin')
                 ) THEN 'critic'
                 ELSE 'audience'
               END AS review_type
        FROM reviews r
        JOIN users u ON u.id=r.user_id
        WHERE r.event_id=$1 AND {PUBLIC_REVIEW_SQL}
        ORDER BY r.published_at ASC
        """,
        event_id,
    )

    reviews = [dict(r) for r in rows]

    critic_scores = [float(r["rating"]) for r in reviews if r["review_type"] == "critic"]
    audience_scores = [float(r["rating"]) for r in reviews if r["review_type"] == "audience"]

    critic_rating = round(sum(critic_scores) / len(critic_scores), 1) if critic_scores else 0.0
    audience_rating = round(sum(audience_scores) / len(audience_scores), 1) if audience_scores else 0.0
    available_scores = [x for x in (critic_scores, audience_scores) if x]
    all_scores = [score for group in available_scores for score in group]
    overall_rating = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0

    try:
        ai = await generate_summary(reviews)
    except RuntimeError:
        logger.exception("AI review summary is unavailable for %s", event_id)
        raise HTTPException(
            status_code=503,
            detail="AI review summaries are temporarily unavailable. Please try again later.",
        )
    except Exception as exc:
        print(f"AI review summary generation failed for {event_id}: {exc!r}")
        raise HTTPException(status_code=502, detail="Unable to generate AI review summary")

    now = datetime.now(timezone.utc)
    await conn.execute(
        """
        INSERT INTO ai_review_summaries (
            event_id, audience_summary, critic_summary, overall_summary,
            audience_liked, audience_disliked, critic_liked, critic_disliked,
            audience_rating, critic_rating, overall_rating,
            review_count, source_review_updated_at, generated_at, updated_at
        )
        VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8::jsonb,
                $9,$10,$11,$12,$13,$14,$14)
        ON CONFLICT (event_id) DO UPDATE SET
            audience_summary=EXCLUDED.audience_summary,
            critic_summary=EXCLUDED.critic_summary,
            overall_summary=EXCLUDED.overall_summary,
            audience_liked=EXCLUDED.audience_liked,
            audience_disliked=EXCLUDED.audience_disliked,
            critic_liked=EXCLUDED.critic_liked,
            critic_disliked=EXCLUDED.critic_disliked,
            audience_rating=EXCLUDED.audience_rating,
            critic_rating=EXCLUDED.critic_rating,
            overall_rating=EXCLUDED.overall_rating,
            review_count=EXCLUDED.review_count,
            source_review_updated_at=EXCLUDED.source_review_updated_at,
            generated_at=EXCLUDED.generated_at,
            updated_at=EXCLUDED.updated_at
        """,
        event_id,
        ai["audience_summary"], ai["critic_summary"], ai["overall_summary"],
        json.dumps(ai.get("audience_liked", [])), json.dumps(ai.get("audience_disliked", [])),
        json.dumps(ai.get("critic_liked", [])), json.dumps(ai.get("critic_disliked", [])),
        audience_rating, critic_rating, overall_rating,
        review_count, source_updated_at, now,
    )

    return {
        "event_id": str(event_id),
        "cached": False,
        "generated_at": now.isoformat(),
        "review_count": review_count,
        "audience_rating": audience_rating,
        "critic_rating": critic_rating,
        "overall_rating": overall_rating,
        **ai,
    }

# ─────────────────────────────────────────────────────────────────────────────
# 2. POST /api/reviews — Submit Review (FR-01, FR-06, FR-12)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def submit_review(
    body: CreateReviewRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    event = await conn.fetchrow("SELECT id FROM events WHERE id=$1", body.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    user_id = current_user["id"]
    user_critic = is_approved_critic(current_user)

    if not user_critic:
        if body.sections:
            raise HTTPException(
                status_code=403,
                detail="Only approved critics can author reviews with structured sections."
            )
        if body.media_url:
            raise HTTPException(
                status_code=403,
                detail="Only approved critics can attach media to reviews."
            )
        if body.scheduled_for:
            raise HTTPException(
                status_code=403,
                detail="Only approved critics can schedule reviews for future publishing."
            )
    else:
        # Enforce configurable word count limits for critic reviews
        total_words = count_words(body.content, body.sections)
        if total_words < CRITIC_MIN_WORDS:
            raise HTTPException(
                status_code=400,
                detail=f"Critic review must be at least {CRITIC_MIN_WORDS} words (currently {total_words} words)."
            )
        if total_words > CRITIC_MAX_WORDS:
            raise HTTPException(
                status_code=400,
                detail=f"Critic review cannot exceed {CRITIC_MAX_WORDS} words (currently {total_words} words)."
            )
        if body.media_url and not (body.media_url.startswith("http://") or body.media_url.startswith("https://")):
            raise HTTPException(
                status_code=400,
                detail="Media attachment must be a valid URL starting with http:// or https://"
            )

    sections_json_str = json.dumps(body.sections) if body.sections else None

    # Scheduled publishing: the review stays hidden until `scheduled_for`
    scheduled_for = None
    if body.scheduled_for is not None:
        if body.is_draft:
            raise HTTPException(status_code=400, detail="A draft cannot be scheduled")
        scheduled_for = validate_schedule(body.scheduled_for)

    # Check if review already exists
    existing = await conn.fetchrow(
        "SELECT id, version FROM reviews WHERE event_id=$1 AND user_id=$2",
        body.event_id, user_id
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="You have already reviewed this event. Edit your existing review instead."
        )

    try:
        async with conn.transaction():
            # Create brand new review
            row = await conn.fetchrow(
                """
                INSERT INTO reviews (event_id, user_id, rating, headline, content, sections_json, media_url, is_spoiler, is_draft, scheduled_for, published_at, version)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, COALESCE($10, now()), 1)
                RETURNING *
                """,
                body.event_id, user_id, body.rating, body.headline, body.content,
                sections_json_str, body.media_url, body.is_spoiler, body.is_draft, scheduled_for
            )

            # Record initial version 1
            await conn.execute(
                """
                INSERT INTO review_versions (review_id, version_number, rating, headline, content, sections_json, is_spoiler, change_summary)
                VALUES ($1, 1, $2, $3, $4, $5, $6, 'Initial critique submission')
                """,
                row["id"], body.rating, body.headline, body.content, sections_json_str, body.is_spoiler
            )

    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status_code=409,
            detail="You have already reviewed this event. Edit your existing review instead."
        )

    # Format return
    roles = current_user.get("roles", [])
    author = ReviewAuthor(
        id=str(user_id),
        name=current_user["name"],
        email=current_user["email"],
        role="critic" if ("critic" in roles or "admin" in roles) else "customer",
        is_verified=bool(current_user.get("is_verified")),
        publication=current_user.get("publication"),
        avatar_url=current_user.get("avatar_url"),
        bio=current_user.get("bio")
    )

    return ReviewOut(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        user_id=str(user_id),
        rating=float(row["rating"]),
        headline=row["headline"],
        content=row["content"],
        sections=body.sections,
        media_url=row["media_url"],
        is_spoiler=row["is_spoiler"],
        is_draft=row["is_draft"],
        scheduled_for=row["scheduled_for"],
        version=row["version"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
        author=author,
        upvotes_count=0,
        has_upvoted=False,
        comments_count=0,
        comments=[],
        versions_count=1
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. PATCH /api/reviews/{review_id} — Edit Review (FR-04, FR-28)
# ─────────────────────────────────────────────────────────────────────────────
@router.patch("/{review_id}", response_model=ReviewOut)
async def update_review(
    review_id: uuid_module.UUID,
    body: UpdateReviewRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    review = await conn.fetchrow(
        """
        SELECT *, (is_draft = false AND scheduled_for IS NOT NULL AND scheduled_for > now()) AS is_scheduled
        FROM reviews WHERE id=$1
        """,
        review_id
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    user_id = current_user["id"]
    roles = current_user.get("roles", [])
    if review["user_id"] != user_id and "admin" not in roles:
        raise HTTPException(status_code=403, detail="Not authorized to edit this review (NFR-11)")

    user_critic = is_approved_critic(current_user)
    if not user_critic:
        if body.sections is not None:
            raise HTTPException(
                status_code=403,
                detail="Only approved critics can author reviews with structured sections."
            )
        if body.media_url is not None:
            raise HTTPException(
                status_code=403,
                detail="Only approved critics can attach media to reviews."
            )
        if body.scheduled_for is not None:
            raise HTTPException(
                status_code=403,
                detail="Only approved critics can schedule reviews for future publishing."
            )

    new_rating = body.rating if body.rating is not None else float(review["rating"])
    new_headline = body.headline if body.headline is not None else review["headline"]
    new_content = body.content if body.content is not None else review["content"]
    new_sections_json = json.dumps(body.sections) if body.sections is not None else review["sections_json"]
    new_media_url = body.media_url if body.media_url is not None else review["media_url"]
    new_spoiler = body.is_spoiler if body.is_spoiler is not None else review["is_spoiler"]

    if user_critic:
        sec_for_count = body.sections if body.sections is not None else (
            json.loads(new_sections_json) if new_sections_json and isinstance(new_sections_json, str) else new_sections_json
        )
        total_words = count_words(new_content, sec_for_count)
        if total_words < CRITIC_MIN_WORDS:
            raise HTTPException(
                status_code=400,
                detail=f"Critic review must be at least {CRITIC_MIN_WORDS} words (currently {total_words} words)."
            )
        if total_words > CRITIC_MAX_WORDS:
            raise HTTPException(
                status_code=400,
                detail=f"Critic review cannot exceed {CRITIC_MAX_WORDS} words (currently {total_words} words)."
            )
        if new_media_url and not (new_media_url.startswith("http://") or new_media_url.startswith("https://")):
            raise HTTPException(
                status_code=400,
                detail="Media attachment must be a valid URL starting with http:// or https://"
            )

    # Visibility. A review is in one of three states:
    #   draft      is_draft = true
    #   scheduled  is_draft = false and scheduled_for is in the future
    #   public     everything else
    # Only a draft or a scheduled review can change state.
    is_draft_now = review["is_draft"]
    is_scheduled_now = review["is_scheduled"]
    can_change_state = is_draft_now or is_scheduled_now

    new_is_draft = is_draft_now
    new_scheduled_for = review["scheduled_for"]
    new_published_at = review["published_at"]

    wants_publish = bool(body.publish_now) or (
        body.is_draft is False and is_draft_now and body.scheduled_for is None
    )
    wants_draft = body.is_draft is True

    if wants_draft and body.scheduled_for is not None:
        raise HTTPException(status_code=400, detail="A draft cannot be scheduled")

    if wants_draft:
        if not can_change_state:
            raise HTTPException(status_code=400, detail="A published review cannot be turned back into a draft")
        new_is_draft = True
        new_scheduled_for = None
    elif wants_publish:
        if not can_change_state:
            raise HTTPException(status_code=400, detail="This review is already published")
        new_is_draft = False
        new_scheduled_for = None
        new_published_at = datetime.now(timezone.utc)
    elif body.scheduled_for is not None:
        if not can_change_state:
            raise HTTPException(status_code=400, detail="Only a draft or scheduled review can be scheduled")
        new_is_draft = False
        new_scheduled_for = validate_schedule(body.scheduled_for)
        new_published_at = new_scheduled_for

    # A new version is recorded only when the text/rating actually changed
        content_changed = (
        new_rating != float(review["rating"])
        or new_headline != review["headline"]
        or new_content != review["content"]
        or new_sections_json != review["sections_json"]
        or new_media_url != review["media_url"]
        or new_spoiler != review["is_spoiler"]
    )
    new_version = review["version"] + 1 if content_changed else review["version"]

    if content_changed:
        # Record historical version in review_versions (FR-28, NFR-16)
        await conn.execute(
            """
            INSERT INTO review_versions (review_id, version_number, rating, headline, content, sections_json, is_spoiler, change_summary)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            review_id, new_version, new_rating, new_headline, new_content, new_sections_json, new_spoiler,
            body.change_summary or f"Updated on {datetime.utcnow().strftime('%b %d, %Y')}"
        )

    row = await conn.fetchrow(
        """
        UPDATE reviews
        SET rating=$1, headline=$2, content=$3, sections_json=$4, is_spoiler=$5, version=$6,
            is_draft=$7, scheduled_for=$8, published_at=$9, media_url=$10, updated_at=now()
        WHERE id=$11
        RETURNING *
        """,
        new_rating, new_headline, new_content, new_sections_json, new_spoiler, new_version,
        new_is_draft, new_scheduled_for, new_published_at, new_media_url, review_id
    )

    author = ReviewAuthor(
        id=str(user_id),
        name=current_user["name"],
        email=current_user["email"],
        role="critic" if ("critic" in roles or "admin" in roles) else "customer",
        is_verified=bool(current_user.get("is_verified")),
        publication=current_user.get("publication"),
        avatar_url=current_user.get("avatar_url")
    )

    return ReviewOut(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        user_id=str(user_id),
        rating=float(row["rating"]),
        headline=row["headline"],
        content=row["content"],
        sections=body.sections,
        media_url=row["media_url"],
        is_spoiler=row["is_spoiler"],
        is_draft=row["is_draft"],
        scheduled_for=row["scheduled_for"],
        version=row["version"],
        published_at=row["published_at"],
        updated_at=row["updated_at"],
        author=author,
        upvotes_count=0,
        has_upvoted=False,
        comments_count=0,
        comments=[],
        versions_count=new_version
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3b. DELETE /api/reviews/{review_id} — Delete Review (owner, admin, or manager for reported reviews)
# ─────────────────────────────────────────────────────────────────────────────
@router.delete("/{review_id}")
async def delete_review(
    review_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    async with conn.transaction():
        review = await conn.fetchrow("SELECT * FROM reviews WHERE id=$1 FOR UPDATE", review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        roles = current_user.get("roles", [])
        is_author = review["user_id"] == current_user["id"]
        if not is_author and "admin" not in roles:
            # A manager may remove a review only when it has been reported
            reported = False
            if "manager" in roles:
                reported = bool(await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM review_reports WHERE review_id=$1)", review_id
                ))
            if not reported:
                raise HTTPException(status_code=403, detail="Not authorized to delete this review")

        # Snapshot everything before the CASCADE wipes it
        versions = await conn.fetch(
            """
            SELECT version_number, rating, headline, content, sections_json,
                   is_spoiler, change_summary, created_at
            FROM review_versions WHERE review_id=$1 ORDER BY version_number
            """,
            review_id
        )
        comments = await conn.fetch(
            """
            SELECT id, parent_comment_id, user_id, content, is_pinned, created_at
            FROM review_comments WHERE review_id=$1 ORDER BY created_at
            """,
            review_id
        )
        upvotes = await conn.fetchval(
            "SELECT COUNT(*) FROM review_upvotes WHERE review_id=$1", review_id
        )

        await conn.execute(
            """
            INSERT INTO review_deletions
                (review_id, event_id, user_id, rating, headline, content, sections_json,
                 media_url, is_spoiler, version, published_at, last_updated_at,
                 versions_snapshot, comments_snapshot, upvotes_count, deleted_by)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            """,
            review["id"], review["event_id"], review["user_id"], review["rating"],
            review["headline"], review["content"], review["sections_json"],
            review["media_url"], review["is_spoiler"], review["version"],
            review["published_at"], review["updated_at"],
            json.dumps([dict(v) for v in versions], default=str),
            json.dumps([dict(c) for c in comments], default=str),
            upvotes, current_user["id"]
        )

        # versions, upvotes and comments are removed by ON DELETE CASCADE
        await conn.execute("DELETE FROM reviews WHERE id=$1", review_id)

    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# 4. POST /api/reviews/{review_id}/upvote — Toggle Upvote (FR-20)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{review_id}/upvote")
async def toggle_upvote(
    review_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    visible = await conn.fetchval(f"SELECT {PUBLIC_REVIEW_SQL} FROM reviews r WHERE r.id=$1", review_id)
    if not visible:
        raise HTTPException(status_code=404, detail="Review not found")

    user_id = current_user["id"]
    existing = await conn.fetchrow(
        "SELECT id FROM review_upvotes WHERE review_id=$1 AND user_id=$2",
        review_id, user_id
    )
    if existing:
        await conn.execute("DELETE FROM review_upvotes WHERE id=$1", existing["id"])
        upvoted = False
    else:
        await conn.execute(
            "INSERT INTO review_upvotes (review_id, user_id) VALUES ($1, $2)",
            review_id, user_id
        )
        upvoted = True

    count = await conn.fetchval("SELECT COUNT(*) FROM review_upvotes WHERE review_id=$1", review_id)
    return {"upvoted": upvoted, "upvotes_count": count}


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /api/reviews/{review_id}/versions & Revert (FR-28, FR-29)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{review_id}/versions", response_model=List[ReviewVersionOut])
async def list_review_versions(
    review_id: uuid_module.UUID,
    current_user: Optional[dict] = Depends(get_optional_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    review = await conn.fetchrow(
        f"SELECT r.user_id, {PUBLIC_REVIEW_SQL} AS is_public FROM reviews r WHERE r.id=$1",
        review_id
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if not review["is_public"]:
        can_see = current_user is not None and (
            review["user_id"] == current_user["id"] or "admin" in current_user.get("roles", [])
        )
        if not can_see:
            raise HTTPException(status_code=404, detail="Review not found")

    rows = await conn.fetch(
        "SELECT * FROM review_versions WHERE review_id=$1 ORDER BY version_number DESC",
        review_id
    )
    return [
        ReviewVersionOut(
            id=str(r["id"]),
            review_id=str(r["review_id"]),
            version_number=r["version_number"],
            rating=float(r["rating"]),
            headline=r["headline"],
            content=r["content"],
            sections_json=json.loads(r["sections_json"]) if r["sections_json"] else None,
            is_spoiler=r["is_spoiler"],
            change_summary=r["change_summary"],
            created_at=r["created_at"]
        ) for r in rows
    ]


@router.post("/{review_id}/revert/{version_id}")
async def revert_review_version(
    review_id: uuid_module.UUID,
    version_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    review = await conn.fetchrow("SELECT * FROM reviews WHERE id=$1", review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    user_id = current_user["id"]
    roles = current_user.get("roles", [])
    if review["user_id"] != user_id and "admin" not in roles:
        raise HTTPException(status_code=403, detail="Not authorized (NFR-11)")

    target_ver = await conn.fetchrow(
        "SELECT * FROM review_versions WHERE id=$1 AND review_id=$2",
        version_id, review_id
    )
    if not target_ver:
        raise HTTPException(status_code=404, detail="Version not found")

    new_version = review["version"] + 1
    await conn.execute(
        """
        INSERT INTO review_versions (review_id, version_number, rating, headline, content, sections_json, is_spoiler, change_summary)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        review_id, new_version, target_ver["rating"], target_ver["headline"], target_ver["content"],
        target_ver["sections_json"], target_ver["is_spoiler"], f"Reverted to Version {target_ver['version_number']}"
    )

    await conn.execute(
        """
        UPDATE reviews
        SET rating=$1, headline=$2, content=$3, sections_json=$4, is_spoiler=$5, version=$6, updated_at=now()
        WHERE id=$7
        """,
        target_ver["rating"], target_ver["headline"], target_ver["content"],
        target_ver["sections_json"], target_ver["is_spoiler"], new_version, review_id
    )
    return {"message": f"Successfully reverted to Version {target_ver['version_number']}"}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Reader Comments & Pinning (FR-18, FR-19)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/{review_id}/comments", response_model=CommentOut)
async def post_comment(
    review_id: uuid_module.UUID,
    body: CommentCreate,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    review = await conn.fetchrow(
        f"SELECT r.id, r.user_id, {PUBLIC_REVIEW_SQL} AS is_public FROM reviews r WHERE r.id=$1",
        review_id
    )
    if not review or not review["is_public"]:
        raise HTTPException(status_code=404, detail="Review not found")

    # Replies: the parent must be a comment on the SAME review. Threads stay one
    # level deep, so a reply to a reply is attached to the original comment.
    parent_id = None
    if body.parent_comment_id is not None:
        parent = await conn.fetchrow(
            "SELECT id, review_id, parent_comment_id FROM review_comments WHERE id=$1",
            body.parent_comment_id
        )
        if not parent or parent["review_id"] != review_id:
            raise HTTPException(status_code=404, detail="Comment to reply to was not found on this review")
        parent_id = parent["parent_comment_id"] or parent["id"]

    user_id = current_user["id"]
    row = await conn.fetchrow(
        """
        INSERT INTO review_comments (review_id, user_id, content, parent_comment_id)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        review_id, user_id, body.content, parent_id
    )

    roles = current_user.get("roles", [])
    is_critic = current_user.get("is_verified") or ("critic" in roles) or ("admin" in roles)

    return CommentOut(
        id=str(row["id"]),
        review_id=str(review_id),
        user_id=str(user_id),
        content=row["content"],
        is_pinned=row["is_pinned"],
        created_at=row["created_at"],
        author_name=current_user["name"],
        author_avatar=current_user.get("avatar_url"),
        is_critic=bool(is_critic),
        parent_comment_id=str(parent_id) if parent_id else None,
        is_review_author=review["user_id"] == user_id
    )


@router.post("/comments/{comment_id}/pin")
async def toggle_pin_comment(
    comment_id: uuid_module.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    comment = await conn.fetchrow(
        "SELECT c.*, r.user_id as review_author_id FROM review_comments c JOIN reviews r ON r.id = c.review_id WHERE c.id=$1",
        comment_id
    )
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    user_id = current_user["id"]
    roles = current_user.get("roles", [])
    if comment["review_author_id"] != user_id and "admin" not in roles:
        raise HTTPException(status_code=403, detail="Only review author can pin comments (FR-19)")

    if comment["parent_comment_id"]:
        raise HTTPException(status_code=400, detail="Only top-level comments can be pinned")

    new_pinned = not comment["is_pinned"]
    await conn.execute("UPDATE review_comments SET is_pinned=$1 WHERE id=$2", new_pinned, comment_id)
    return {"id": str(comment_id), "is_pinned": new_pinned}


# ─────────────────────────────────────────────────────────────────────────────
# 7. Export Review (FR-32)
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{review_id}/export")
async def export_review(
    review_id: uuid_module.UUID,
    format: str = Query("txt", pattern="^(txt|markdown)$"),
    conn: asyncpg.Connection = Depends(get_conn)
):
    row = await conn.fetchrow(
        f"""
        SELECT r.*, e.title as event_title, u.name as author_name, u.publication
        FROM reviews r
        JOIN events e ON e.id = r.event_id
        JOIN users u ON u.id = r.user_id
        WHERE r.id=$1 AND {PUBLIC_REVIEW_SQL}
        """,
        review_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")

    pub_name = row["publication"] or "Independent Film Critic"
    text = f"""# {row['event_title']} — Film Critique
By {row['author_name']} ({pub_name})
Published: {row['published_at'].strftime('%B %d, %Y')}
Rating: {row['rating']}/10 ({'Certified Fresh' if float(row['rating']) >= 6.0 else 'Rotten'})

## Headline / Verdict
"{row['headline']}"

## Full Critique
{row['content']}

------------------------------------------------------
Exported from TicketFlow Cinema Discovery & Review Module
"""
    media_type = "text/markdown" if format == "markdown" else "text/plain"
    return Response(
        content=text,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="critique-{review_id}.{format}"'}
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. Report a review + Manager moderation
# ─────────────────────────────────────────────────────────────────────────────
class ReportCreate(BaseModel):
    reason: str = Field(..., pattern="^(spam|abusive|spoiler|off_topic|other)$")
    details: Optional[str] = Field(None, max_length=500)


class ReportResolve(BaseModel):
    status: str = Field(..., pattern="^(dismissed|reviewed)$")


def require_moderator(current_user: dict = Depends(get_current_user)) -> dict:
    roles = current_user.get("roles", [])
    if "manager" not in roles and "admin" not in roles:
        raise HTTPException(status_code=403, detail="Managers only")
    return current_user


@router.post("/{review_id}/report", status_code=status.HTTP_201_CREATED)
async def report_review(
    review_id: uuid_module.UUID,
    body: ReportCreate,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn)
):
    review = await conn.fetchrow(
        f"SELECT r.user_id, {PUBLIC_REVIEW_SQL} AS is_public FROM reviews r WHERE r.id=$1",
        review_id
    )
    if not review or not review["is_public"]:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["user_id"] == current_user["id"]:
        raise HTTPException(status_code=400, detail="You cannot report your own review")

    details = body.details.strip() if body.details else None
    try:
        await conn.execute(
            "INSERT INTO review_reports (review_id, reporter_id, reason, details) VALUES ($1, $2, $3, $4)",
            review_id, current_user["id"], body.reason, details or None
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="You have already reported this review")
    return {"reported": True}


@router.get("/reports")
async def list_review_reports(
    status_filter: str = Query("open", alias="status", pattern="^(open|all)$"),
    moderator: dict = Depends(require_moderator),
    conn: asyncpg.Connection = Depends(get_conn)
):
    """One entry per reported review, newest report first, with every report on it."""
    where_open = "WHERE rp.status = 'open'" if status_filter == "open" else ""
    rows = await conn.fetch(
        f"""
        SELECT rp.id, rp.review_id, rp.reason, rp.details, rp.status, rp.created_at,
               rep.name AS reporter_name,
               r.rating, r.headline, r.content, r.is_spoiler, r.event_id,
               e.title AS event_title,
               au.name AS author_name,
               ({PUBLIC_REVIEW_SQL}) AS is_public
        FROM review_reports rp
        JOIN reviews r  ON r.id  = rp.review_id
        JOIN events e   ON e.id  = r.event_id
        JOIN users au   ON au.id = r.user_id
        JOIN users rep  ON rep.id = rp.reporter_id
        {where_open}
        ORDER BY rp.created_at DESC
        """
    )
    grouped: Dict[str, dict] = {}
    for row in rows:
        key = str(row["review_id"])
        item = grouped.get(key)
        if item is None:
            item = grouped[key] = {
                "review_id": key,
                "event_id": str(row["event_id"]),
                "event_title": row["event_title"],
                "author_name": row["author_name"],
                "rating": float(row["rating"]),
                "headline": row["headline"],
                "content": row["content"],
                "is_spoiler": row["is_spoiler"],
                "is_public": bool(row["is_public"]),
                "latest_report_at": row["created_at"].isoformat(),
                "open_count": 0,
                "reports": [],
            }
        if row["status"] == "open":
            item["open_count"] += 1
        item["reports"].append({
            "id": str(row["id"]),
            "reason": row["reason"],
            "details": row["details"],
            "status": row["status"],
            "reporter_name": row["reporter_name"],
            "created_at": row["created_at"].isoformat(),
        })
    return {"items": list(grouped.values())}


@router.patch("/reports/{review_id}")
async def resolve_review_reports(
    review_id: uuid_module.UUID,
    body: ReportResolve,
    moderator: dict = Depends(require_moderator),
    conn: asyncpg.Connection = Depends(get_conn)
):
    """Close every open report on a review: 'dismissed' (no action) or 'reviewed' (handled)."""
    result = await conn.execute(
        """
        UPDATE review_reports
        SET status=$1, resolved_at=now(), resolved_by=$2
        WHERE review_id=$3 AND status='open'
        """,
        body.status, moderator["id"], review_id
    )
    updated = int(result.split()[-1])
    if updated == 0:
        raise HTTPException(status_code=404, detail="No open reports for this review")
    return {"updated": updated, "status": body.status}


# ─────────────────────────────────────────────────────────────────────────────
# 16. GET /api/reviews/critics/{critic_id} — Public Critic Profile
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/critics/{critic_id}", response_model=CriticProfileOut)
async def get_critic_profile(
    critic_id: uuid_module.UUID,
    conn: asyncpg.Connection = Depends(get_conn)
):
    """
    Public profile showing the critic's photo, name, bio, publication,
    published reviews, and rating history.
    """
    user_row = await conn.fetchrow(
        """
        SELECT u.id, u.name, u.email, u.publication, u.avatar_url, u.bio,
               array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        LEFT JOIN roles r ON r.id = ur.role_id
        WHERE u.id = $1 AND u.status = 'active'
        GROUP BY u.id
        """,
        critic_id
    )
    if not user_row:
        raise HTTPException(status_code=404, detail="Critic not found")

    roles = user_row["roles"] or []
    if "critic" not in roles and "admin" not in roles:
        raise HTTPException(status_code=404, detail="User is not an approved critic")

    # Fetch published critic reviews with event info
    review_rows = await conn.fetch(
        f"""
        SELECT r.id, r.event_id, r.rating, r.headline, r.content, r.sections_json,
               r.media_url, r.is_spoiler, r.version, r.published_at, r.updated_at,
               e.title as event_title, e.poster_url as event_poster, e.genre as event_genre,
               COUNT(DISTINCT up.user_id) as upvotes_count
        FROM reviews r
        JOIN events e ON e.id = r.event_id
        LEFT JOIN review_upvotes up ON up.review_id = r.id
        WHERE r.user_id = $1 AND {PUBLIC_REVIEW_SQL}
        GROUP BY r.id, e.id
        ORDER BY r.published_at DESC
        """,
        critic_id
    )

    ratings = [float(r["rating"]) for r in review_rows]
    total_reviews = len(ratings)
    avg_rating = round(sum(ratings) / total_reviews, 1) if total_reviews > 0 else 0.0
    fresh_count = sum(1 for s in ratings if s >= 6.0)
    fresh_pct = int(round((fresh_count / total_reviews) * 100)) if total_reviews > 0 else 0

    # Rating distribution 1..10
    rating_history: Dict[str, int] = {str(i): 0 for i in range(1, 11)}
    for s in ratings:
        k = str(min(10, max(1, round(s))))
        rating_history[k] = rating_history.get(k, 0) + 1

    formatted_reviews = []
    for r in review_rows:
        sections_dict = None
        if r["sections_json"]:
            try:
                sections_dict = json.loads(r["sections_json"]) if isinstance(r["sections_json"], str) else r["sections_json"]
            except Exception:
                sections_dict = None
        formatted_reviews.append({
            "id": str(r["id"]),
            "event_id": str(r["event_id"]),
            "event_title": r["event_title"],
            "event_poster": r["event_poster"],
            "event_genre": r["event_genre"],
            "rating": float(r["rating"]),
            "headline": r["headline"],
            "content": r["content"],
            "sections": sections_dict,
            "media_url": r["media_url"],
            "is_spoiler": r["is_spoiler"],
            "published_at": r["published_at"].isoformat() if r["published_at"] else None,
            "upvotes_count": r["upvotes_count"]
        })

    return CriticProfileOut(
        id=str(user_row["id"]),
        name=user_row["name"],
        publication=user_row["publication"],
        avatar_url=user_row["avatar_url"],
        bio=user_row["bio"],
        role="critic",
        total_reviews=total_reviews,
        average_rating=avg_rating,
        fresh_percentage=fresh_pct,
        rating_history=rating_history,
        reviews=formatted_reviews
    )
