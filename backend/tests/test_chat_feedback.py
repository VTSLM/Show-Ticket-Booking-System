import pytest
import asyncpg
from fastapi import HTTPException

from routers import chat


class FakeConn:
    def __init__(self, error=None):
        self.error = error
        self.execute_calls = []

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))

        if self.error:
            raise self.error

        return "INSERT 0 1"


class FakePool:
    """Fake asyncpg pool that returns a FakeConn from acquire()."""

    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeResolved:
    """Small awaitable wrapper used to mock async get_pool()."""

    def __init__(self, value):
        self.value = value

    def __await__(self):
        async def _resolve():
            return self.value

        return _resolve().__await__()


def _resolved(value):
    return FakeResolved(value)


@pytest.mark.asyncio
async def test_feedback_accepts_positive_rating(monkeypatch):
    conn = FakeConn()

    monkeypatch.setattr(
        chat,
        "get_pool",
        lambda: _resolved(FakePool(conn)),
    )

    monkeypatch.setattr(
        chat,
        "get_optional_user",
        lambda auth, conn: _resolved(
            {"id": "user-1", "status": "active"}
        ),
    )

    body = chat.ChatFeedbackRequest(
        reply_id="123e4567-e89b-12d3-a456-426614174000",
        rating=1,
    )

    result = await chat.chat_feedback(body, None)

    assert result["ok"] is True
    assert len(conn.execute_calls) == 1

    query, args = conn.execute_calls[0]

    assert "chat_feedback" in query
    assert str(args[0]) == "123e4567-e89b-12d3-a456-426614174000"
    assert args[1] == "user-1"
    assert args[2] == 1


@pytest.mark.asyncio
async def test_feedback_from_a_guest_is_refused(monkeypatch):
    conn = FakeConn()

    monkeypatch.setattr(
        chat,
        "get_pool",
        lambda: _resolved(FakePool(conn)),
    )

    monkeypatch.setattr(
        chat,
        "get_optional_user",
        lambda auth, conn: _resolved(None),
    )

    body = chat.ChatFeedbackRequest(
        reply_id="123e4567-e89b-12d3-a456-426614174001",
        rating=-1,
    )

    with pytest.raises(HTTPException) as err:
        await chat.chat_feedback(body, None)

    assert err.value.status_code == 401
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_feedback_rejects_duplicate_reply(monkeypatch):
    conn = FakeConn(
        error=asyncpg.UniqueViolationError("duplicate")
    )

    monkeypatch.setattr(
        chat,
        "get_pool",
        lambda: _resolved(FakePool(conn)),
    )

    monkeypatch.setattr(
        chat,
        "get_optional_user",
        lambda auth, conn: _resolved({"id": "user-1", "status": "active"}),
    )

    body = chat.ChatFeedbackRequest(
        reply_id="123e4567-e89b-12d3-a456-426614174002",
        rating=1,
    )

    with pytest.raises(HTTPException) as exc:
        await chat.chat_feedback(body, None)

    assert exc.value.status_code == 409


def test_feedback_rejects_invalid_rating():
    with pytest.raises(Exception):
        chat.ChatFeedbackRequest(
            reply_id="123e4567-e89b-12d3-a456-426614174003",
            rating=0,
        )


def test_feedback_rejects_invalid_reply_id():
    with pytest.raises(Exception):
        chat.ChatFeedbackRequest(
            reply_id="not-a-valid-uuid",
            rating=1,
        )