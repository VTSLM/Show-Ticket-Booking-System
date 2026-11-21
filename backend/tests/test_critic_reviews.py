import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException

from routers.reviews import (
    submit_review,
    get_critic_profile,
)
from schemas.reviews import CreateReviewRequest


def _user(role="customer", is_verified=False):
    return {
        "id": str(uuid.uuid4()),
        "name": f"Test {role.capitalize()}",
        "email": f"{role}@ticketflow.test",
        "roles": [role] if role else [],
        "is_verified": is_verified,
        "publication": "Daily Review" if role == "critic" else None,
        "avatar_url": None,
        "bio": "Movie lover" if role == "critic" else None,
    }


def _conn():
    conn = AsyncMock()
    @asynccontextmanager
    async def _tx():
        yield
    conn.transaction = _tx
    return conn


@pytest.mark.asyncio
async def test_regular_user_cannot_submit_review_sections():
    conn = _conn()
    conn.fetchrow.return_value = {"id": str(uuid.uuid4())}  # event exists
    user = _user("customer")
    req = CreateReviewRequest(
        event_id=uuid.uuid4(),
        rating=8.0,
        headline="Great movie",
        content="This movie was really enjoyable and exciting to watch with family.",
        sections={"Story": "Engaging plot and twists."}
    )
    with pytest.raises(HTTPException) as exc:
        await submit_review(body=req, current_user=user, conn=conn)
    assert exc.value.status_code == 403
    assert "structured sections" in exc.value.detail


@pytest.mark.asyncio
async def test_regular_user_cannot_attach_media():
    conn = _conn()
    conn.fetchrow.return_value = {"id": str(uuid.uuid4())}
    user = _user("customer")
    req = CreateReviewRequest(
        event_id=uuid.uuid4(),
        rating=8.0,
        headline="Great movie",
        content="This movie was really enjoyable and exciting to watch with family.",
        media_url="https://youtube.com/watch?v=123"
    )
    with pytest.raises(HTTPException) as exc:
        await submit_review(body=req, current_user=user, conn=conn)
    assert exc.value.status_code == 403
    assert "attach media" in exc.value.detail


@pytest.mark.asyncio
async def test_verified_customer_is_not_classified_as_critic():
    conn = _conn()
    conn.fetchrow.return_value = {"id": str(uuid.uuid4())}
    # User has is_verified=True (account phone/email verified), but role is customer
    user = _user("customer", is_verified=True)
    req = CreateReviewRequest(
        event_id=uuid.uuid4(),
        rating=8.0,
        headline="Great movie",
        content="This movie was really enjoyable and exciting to watch with family.",
        sections={"Story": "Engaging plot and twists."}
    )
    with pytest.raises(HTTPException) as exc:
        await submit_review(body=req, current_user=user, conn=conn)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_critic_word_count_minimum_enforced():
    conn = _conn()
    conn.fetchrow.return_value = {"id": str(uuid.uuid4())}
    critic = _user("critic")
    # Only 5 words (< CRITIC_MIN_WORDS default 10)
    req = CreateReviewRequest(
        event_id=uuid.uuid4(),
        rating=9.0,
        headline="Superb cinematic feat",
        content="Too short review for critic."
    )
    with pytest.raises(HTTPException) as exc:
        await submit_review(body=req, current_user=critic, conn=conn)
    assert exc.value.status_code == 400
    assert "at least 10 words" in exc.value.detail


@pytest.mark.asyncio
async def test_critic_word_count_maximum_enforced():
    conn = _conn()
    conn.fetchrow.return_value = {"id": str(uuid.uuid4())}
    critic = _user("critic")
    # > 1000 words
    req = CreateReviewRequest(
        event_id=uuid.uuid4(),
        rating=9.0,
        headline="Superb cinematic feat",
        content="word " * 1050
    )
    with pytest.raises(HTTPException) as exc:
        await submit_review(body=req, current_user=critic, conn=conn)
    assert exc.value.status_code == 400
    assert "cannot exceed 1000 words" in exc.value.detail


@pytest.mark.asyncio
async def test_critic_review_creation_succeeds_with_sections_and_media():
    conn = _conn()
    event_id = uuid.uuid4()
    critic = _user("critic")
    rev_id = str(uuid.uuid4())

    # event lookup then existing check then insert
    conn.fetchrow.side_effect = [
        {"id": event_id},  # event check
        None,              # existing review check
        {                  # INSERT INTO reviews returning *
            "id": rev_id,
            "event_id": str(event_id),
            "user_id": critic["id"],
            "rating": 9.0,
            "headline": "A Masterpiece of Direction",
            "content": "An extraordinary cinema experience that completely revitalizes modern filmmaking with sheer ambition.",
            "sections_json": '{"Story": "Compelling narrative.", "Verdict": "Must watch."}',
            "media_url": "https://youtube.com/watch?v=sample-trailer",
            "is_spoiler": False,
            "is_draft": False,
            "scheduled_for": None,
            "version": 1,
            "published_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    req = CreateReviewRequest(
        event_id=event_id,
        rating=9.0,
        headline="A Masterpiece of Direction",
        content="An extraordinary cinema experience that completely revitalizes modern filmmaking with sheer ambition.",
        sections={"Story": "Compelling narrative.", "Verdict": "Must watch."},
        media_url="https://youtube.com/watch?v=sample-trailer"
    )

    res = await submit_review(body=req, current_user=critic, conn=conn)
    assert res.id == rev_id
    assert res.author.role == "critic"
    assert res.media_url == "https://youtube.com/watch?v=sample-trailer"


@pytest.mark.asyncio
async def test_public_critic_profile_success():
    conn = _conn()
    critic_id = uuid.uuid4()
    event_id = uuid.uuid4()

    conn.fetchrow.return_value = {
        "id": critic_id,
        "name": "Jane Critic",
        "email": "jane@variety.com",
        "publication": "Variety Weekly",
        "avatar_url": "https://example.com/avatar.jpg",
        "bio": "Film critic with 15 years experience.",
        "roles": ["critic"]
    }

    conn.fetch.return_value = [
        {
            "id": uuid.uuid4(),
            "event_id": event_id,
            "event_title": "Interstellar",
            "event_poster": "https://example.com/poster.jpg",
            "event_genre": "Sci-Fi",
            "rating": 9.5,
            "headline": "Breathtaking Space Odyssey",
            "content": "A wondrous trip across the cosmos.",
            "sections_json": '{"Direction": "Christopher Nolan at his peak"}',
            "media_url": "https://youtube.com/watch?v=interstellar",
            "is_spoiler": False,
            "version": 1,
            "published_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "upvotes_count": 42
        }
    ]

    profile = await get_critic_profile(critic_id=critic_id, conn=conn)
    assert profile.name == "Jane Critic"
    assert profile.publication == "Variety Weekly"
    assert profile.total_reviews == 1
    assert profile.average_rating == 9.5
    assert profile.fresh_percentage == 100
    assert len(profile.reviews) == 1
    assert profile.reviews[0]["event_title"] == "Interstellar"


@pytest.mark.asyncio
async def test_public_critic_profile_404_for_non_critic():
    conn = _conn()
    user_id = uuid.uuid4()
    conn.fetchrow.return_value = {
        "id": user_id,
        "name": "John Customer",
        "email": "john@example.com",
        "publication": None,
        "avatar_url": None,
        "bio": None,
        "roles": ["customer"]
    }
    with pytest.raises(HTTPException) as exc:
        await get_critic_profile(critic_id=user_id, conn=conn)
    assert exc.value.status_code == 404
    assert "not an approved critic" in exc.value.detail
