"""POST /api/chat: the TicketFlow assistant."""

import json
from typing import List, Literal, Optional
from uuid import UUID

import asyncpg

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from database import get_pool
from services.chatbot_tools import _is_uuid as is_uuid
from routers.reviews import get_optional_user, optional_security
from services import chatbot


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


MAX_MESSAGE = 500


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=4000,
    )


class ChatContext(BaseModel):
    event_id: Optional[str] = None
    show_id: Optional[str] = None
    booking_id: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=MAX_MESSAGE,
    )

    history: List[ChatMessage] = Field(
        default_factory=list,
        max_length=10,
    )

    context: Optional[ChatContext] = None

    @field_validator("message")
    @classmethod
    def not_blank(
        cls,
        value: str,
    ) -> str:

        value = value.strip()

        if not value:
            raise ValueError(
                "Message is empty"
            )

        return value


class ChatFeedbackRequest(BaseModel):
    reply_id: UUID
    rating: Literal[-1, 1]


class ChatLogQuery(BaseModel):
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
    )

    provider: Optional[str] = None
    model: Optional[str] = None


async def _prepare_request(
    body: ChatRequest,
    auth: Optional[
        HTTPAuthorizationCredentials
    ],
):
    """
    Resolve the user and page context.

    No request-long database connection is held while the model answers.
    """

    pool = await get_pool()

    async with pool.acquire() as conn:
        user = await get_optional_user(
            auth,
            conn,
        )

    if user and user.get("status") != "active":
        user = None

    context = {
        key: value
        for key, value in (
            body.context.model_dump()
            if body.context
            else {}
        ).items()
        if value and is_uuid(value)
    }

    history = [
        message.model_dump()
        for message in body.history
    ]

    return (
        user,
        context,
        history,
        pool,
    )


UNAVAILABLE = (
    "The assistant isn't available right now. "
    "Please try again later."
)


@router.post("")
async def chat(
    body: ChatRequest,
    auth: Optional[
        HTTPAuthorizationCredentials
    ] = Depends(optional_security),
):

    user, context, history, pool = (
        await _prepare_request(
            body,
            auth,
        )
    )

    try:
        reply = await chatbot.answer(
            body.message,
            history,
            context,
            user,
            pool,
        )

    except chatbot.AssistantUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                chatbot.BUSY_REPLY
                if exc.busy
                else UNAVAILABLE
            ),
        )

    return {
        "reply": reply,
    }


# ---------------------------------------------------------------------------
# Feature 4: reply feedback
# ---------------------------------------------------------------------------

@router.post("/feedback")
async def chat_feedback(
    body: ChatFeedbackRequest,
    auth: Optional[
        HTTPAuthorizationCredentials
    ] = Depends(optional_security),
):
    """
    Store one helpful/not-helpful vote.

    Only the reply UUID, internal user ID and rating are stored.
    The assistant message itself is never stored.
    """

    pool = await get_pool()

    async with pool.acquire() as conn:

        user = await get_optional_user(
            auth,
            conn,
        )

        if (
            user
            and user.get("status")
            != "active"
        ):
            user = None

        try:
            await conn.execute(
                """
                INSERT INTO chat_feedback (
                    reply_id,
                    user_id,
                    rating
                )
                VALUES ($1, $2, $3)
                """,
                body.reply_id,
                (
                    user.get("id")
                    if user
                    else None
                ),
                body.rating,
            )

        except asyncpg.UniqueViolationError:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Feedback has already been "
                    "submitted for this reply."
                ),
            )

    return {
        "ok": True,
    }


# ---------------------------------------------------------------------------
# Feature 5: admin reply-log query
# ---------------------------------------------------------------------------

def _is_admin(user: Optional[dict]) -> bool:
    """
    Accept both common role shapes used by the project:

        {"role": "admin"}

    or

        {"roles": ["admin", ...]}
    """

    if not user:
        return False

    role = str(
        user.get("role")
        or ""
    ).lower()

    if role == "admin":
        return True

    roles = user.get(
        "roles",
        [],
    )

    if isinstance(
        roles,
        str,
    ):
        roles = [
            roles
        ]

    return any(
        str(item).lower()
        == "admin"
        for item in roles
    )


@router.get("/logs")
async def chat_logs(
    query: ChatLogQuery = Depends(),
    auth: Optional[
        HTTPAuthorizationCredentials
    ] = Depends(optional_security),
):
    """
    Admin-only metadata/metrics view.

    No message text or assistant reply content is returned.
    """

    pool = await get_pool()

    async with pool.acquire() as conn:

        user = await get_optional_user(
            auth,
            conn,
        )

        if (
            user
            and user.get("status")
            != "active"
        ):
            user = None

        if not _is_admin(user):
            raise HTTPException(
                status_code=403,
                detail="Admin access required.",
            )

        conditions = []
        args = []

        if query.provider:
            args.append(
                query.provider
            )

            conditions.append(
                f"provider = ${len(args)}"
            )

        if query.model:
            args.append(
                query.model
            )

            conditions.append(
                f"model = ${len(args)}"
            )

        where = ""

        if conditions:
            where = (
                "WHERE "
                + " AND ".join(
                    conditions
                )
            )

        args.append(
            query.limit
        )

        limit_position = len(args)

        rows = await conn.fetch(
            f"""
            SELECT
                id,
                reply_id,
                provider,
                model,
                tools_used,
                ttft_ms,
                total_time_ms,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost_usd,
                created_at
            FROM public.chat_reply_logs
            {where}
            ORDER BY created_at DESC
            LIMIT ${limit_position}
            """,
            *args,
        )

    return {
        "logs": [
            dict(row)
            for row in rows
        ]
    }


# ---------------------------------------------------------------------------
# Streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    auth: Optional[
        HTTPAuthorizationCredentials
    ] = Depends(optional_security),
):

    user, context, history, pool = (
        await _prepare_request(
            body,
            auth,
        )
    )

    try:
        # Fail before SSE starts.
        chatbot._get_client()

    except chatbot.AssistantUnavailable:
        raise HTTPException(
            status_code=503,
            detail=UNAVAILABLE,
        )

    async def events():

        async for event in chatbot.answer_stream(
            body.message,
            history,
            context,
            user,
            pool,
        ):
            yield (
                "data: "
                + json.dumps(
                    event,
                    ensure_ascii=False,
                )
                + "\n\n"
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )