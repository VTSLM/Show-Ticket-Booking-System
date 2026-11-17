"""Only active accounts may use authenticated endpoints.

Pending (inactive) managers and blocked users must be refused by the shared
`get_current_user` dependency, and treated as anonymous where login is optional.
The database connection is a small fake; no network or Firebase is used.
"""

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import dependencies
from routers import reviews


class FakeConn:
    def __init__(self, row):
        self.row = row

    async def fetchrow(self, query, *args):
        return self.row


def _row(status, roles=("customer",)):
    return {
        "id": "user-1",
        "firebase_uid": "uid-1",
        "name": "Test User",
        "email": "user@example.com",
        "phone": None,
        "birthdate": None,
        "status": status,
        "is_verified": False,
        "publication": None,
        "avatar_url": None,
        "bio": None,
        "roles": list(roles),
    }


def test_active_user_is_allowed():
    user = asyncio.run(dependencies.get_current_user("uid-1", FakeConn(_row("active"))))
    assert user["status"] == "active"
    assert user["roles"] == ["customer"]


@pytest.mark.parametrize(
    "status, detail",
    [("inactive", "Account pending admin approval"), ("blocked", "Account blocked")],
)
def test_non_active_user_is_refused(status, detail):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dependencies.get_current_user("uid-1", FakeConn(_row(status, ("manager",)))))
    assert exc.value.status_code == 403
    assert exc.value.detail == detail


def test_unknown_user_still_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dependencies.get_current_user("uid-unknown", FakeConn(None)))
    assert exc.value.status_code == 404


@pytest.mark.parametrize("status, expected_anonymous", [("active", False), ("inactive", True), ("blocked", True)])
def test_optional_login_on_reviews(monkeypatch, status, expected_anonymous):
    monkeypatch.setattr(reviews, "verify_firebase_token", lambda token: {"uid": "uid-1"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    user = asyncio.run(reviews.get_optional_user(creds, FakeConn(_row(status))))
    assert (user is None) is expected_anonymous
