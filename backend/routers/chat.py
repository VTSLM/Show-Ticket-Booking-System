"""POST /api/chat: the TicketFlow assistant (services/chatbot.py)."""
import json
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

from database import get_pool
from services.chatbot_tools import _is_uuid as is_uuid
from routers.reviews import get_optional_user, optional_security
from services import chatbot

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_MESSAGE = 500


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatContext(BaseModel):
    event_id: Optional[str] = None
    show_id: Optional[str] = None
    booking_id: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    history: List[ChatMessage] = Field(default_factory=list, max_length=10)
    context: Optional[ChatContext] = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message is empty")
        return value


async def _prepare_request(body: ChatRequest, auth: Optional[HTTPAuthorizationCredentials]):
    """Resolve the user and the page context. Returns (user, context, history, pool)."""
    # No request-long database connection: a reply can take several seconds of
    # OpenAI time, so connections are borrowed only while a lookup runs.
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await get_optional_user(auth, conn)
    if user and user.get("status") != "active":
        user = None  # blocked or unapproved accounts are treated as guests
    context = {k: v for k, v in (body.context.model_dump() if body.context else {}).items()
               if v and is_uuid(v)}
    history = [m.model_dump() for m in body.history]
    return user, context, history, pool


UNAVAILABLE = "The assistant isn't available right now. Please try again later."


@router.post("")
async def chat(
    body: ChatRequest,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    user, context, history, pool = await _prepare_request(body, auth)
    try:
        reply = await chatbot.answer(body.message, history, context, user, pool)
    except chatbot.AssistantUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    return {"reply": reply}


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    """Server-sent events: `data: {"type": "status"|"delta"|"done"|"error", ...}`."""
    user, context, history, pool = await _prepare_request(body, auth)
    try:
        chatbot._get_client()  # fail with 503 before the stream starts
    except chatbot.AssistantUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE)

    async def events():
        async for event in chatbot.answer_stream(body.message, history, context, user, pool):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
