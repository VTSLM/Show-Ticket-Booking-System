"""
TicketFlow — Pydantic Schemas for Critics & Reviews Module
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import uuid as uuid_module


class ReviewAuthor(BaseModel):
    id: str
    name: str
    email: str
    role: str = "customer"
    is_verified: bool = False
    publication: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class CommentOut(BaseModel):
    id: str
    review_id: str
    user_id: str
    content: str
    is_pinned: bool = False
    created_at: datetime
    author_name: str
    author_avatar: Optional[str] = None
    is_critic: bool = False


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content")
    @classmethod
    def clean_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment cannot be blank")
        return v


class ReviewVersionOut(BaseModel):
    id: str
    review_id: str
    version_number: int
    rating: float
    headline: str
    content: str
    sections_json: Optional[Dict[str, str]] = None
    is_spoiler: bool
    change_summary: Optional[str] = None
    created_at: datetime


class ReviewBase(BaseModel):
    rating: float = Field(ge=1.0, le=10.0, description="Score on 1.0 to 10.0 scale")
    headline: str = Field(min_length=3, max_length=255, description="One-line summary or verdict (FR-11)")
    content: str = Field(min_length=10, description="Full critique body")
    sections: Optional[Dict[str, str]] = None  # Story, Direction, Performances, etc. (FR-09)
    media_url: Optional[str] = None            # Trailer/Clip link (FR-14)
    is_spoiler: bool = False                   # Spoiler flag (FR-12)


class CreateReviewRequest(ReviewBase):
    event_id: uuid_module.UUID


class UpdateReviewRequest(BaseModel):
    rating: Optional[float] = Field(None, ge=1.0, le=10.0)
    headline: Optional[str] = Field(None, min_length=3, max_length=255)
    content: Optional[str] = Field(None, min_length=10)
    sections: Optional[Dict[str, str]] = None
    media_url: Optional[str] = None
    is_spoiler: Optional[bool] = None
    change_summary: Optional[str] = None


class ReviewOut(ReviewBase):
    id: str
    event_id: str
    user_id: str
    version: int
    published_at: datetime
    updated_at: datetime
    author: ReviewAuthor
    upvotes_count: int = 0
    has_upvoted: bool = False
    comments_count: int = 0
    comments: List[CommentOut] = Field(default_factory=list)
    versions_count: int = 0


class MovieAggregatesOut(BaseModel):
    average_critic_score: float = 0.0
    critic_fresh_percentage: int = 0
    total_critic_reviews: int = 0
    average_user_score: float = 0.0
    user_fresh_percentage: int = 0
    total_user_reviews: int = 0


class EventReviewsResponse(BaseModel):
    event_id: str
    aggregates: MovieAggregatesOut
    reviews: List[ReviewOut]
