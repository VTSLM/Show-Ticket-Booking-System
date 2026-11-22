"""Email verification before using the app (#208)."""
import asyncio
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import config
import dependencies
from firebase_admin_setup import EMAIL_NOT_VERIFIED, is_email_verified
from routers import auth, reviews

VERIFIED = {"uid": "uid-1", "email": "user@example.com", "email_verified": True}
UNVERIFIED = {"uid": "uid-1", "email": "user@example.com", "email_verified": False}
GOOGLE = {"uid": "uid-2", "email": "user@gmail.com", "email_verified": True,
          "firebase": {"sign_in_provider": "google.com"}}


@pytest.fixture
def required(monkeypatch):
    monkeypatch.setattr(config, "EMAIL_VERIFICATION_REQUIRED", True)


class FakeConn:
    def __init__(self, row=None):
        self.row = row
        self.queries = []

    async def fetchrow(self, query, *args):
        self.queries.append(query)
        return self.row

    async def fetchval(self, query, *args):
        self.queries.append(query)
        return "new-id"

    async def execute(self, query, *args):
        self.queries.append(query)


def creds():
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")


# ── the rule ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "decoded, expected",
    [
        (VERIFIED, True),
        (GOOGLE, True),
        (UNVERIFIED, False),
        ({"uid": "uid-1", "email": "user@example.com"}, False),  # claim missing
        ({"uid": "uid-1"}, True),                                # no email to verify
    ],
)
def test_is_email_verified(required, decoded, expected):
    assert is_email_verified(decoded) is expected


def test_switching_the_check_off_lets_everyone_in(monkeypatch):
    monkeypatch.setattr(config, "EMAIL_VERIFICATION_REQUIRED", False)
    assert is_email_verified(UNVERIFIED) is True


# ── protected endpoints ─────────────────────────────────────────────────────

def test_protected_endpoints_refuse_unverified_accounts(required, monkeypatch):
    monkeypatch.setattr(dependencies, "verify_firebase_token", lambda token: UNVERIFIED)
    with pytest.raises(HTTPException) as err:
        asyncio.run(dependencies.get_current_firebase_uid(creds()))
    assert err.value.status_code == 403
    assert err.value.detail == EMAIL_NOT_VERIFIED


@pytest.mark.parametrize("decoded", [VERIFIED, GOOGLE])
def test_protected_endpoints_accept_verified_accounts(required, monkeypatch, decoded):
    monkeypatch.setattr(dependencies, "verify_firebase_token", lambda token: decoded)
    assert asyncio.run(dependencies.get_current_firebase_uid(creds())) == decoded["uid"]


def test_optional_login_treats_unverified_accounts_as_guests(required, monkeypatch):
    monkeypatch.setattr(reviews, "verify_firebase_token", lambda token: UNVERIFIED)
    conn = FakeConn({"id": "user-1", "status": "active", "roles": ["customer"]})
    assert asyncio.run(reviews.get_optional_user(creds(), conn)) is None
    assert conn.queries == []  # the profile isn't even looked up


# ── login ───────────────────────────────────────────────────────────────────

def test_login_refuses_unverified_accounts_before_creating_a_session(required, monkeypatch):
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token: UNVERIFIED)
    conn = FakeConn({"id": "user-1", "status": "active", "roles": ["customer"]})
    with pytest.raises(HTTPException) as err:
        asyncio.run(auth.verify_token({"id_token": "token"}, conn))
    assert err.value.status_code == 403
    assert err.value.detail == EMAIL_NOT_VERIFIED
    assert conn.queries == []  # no profile lookup, no session


def test_login_works_once_verified(required, monkeypatch):
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token: VERIFIED)
    conn = FakeConn({"id": "user-1", "name": "U", "email": "user@example.com", "phone": None,
                     "birthdate": None, "status": "active", "roles": ["customer"]})
    result = asyncio.run(auth.verify_token({"id_token": "token"}, conn))
    assert result["firebase_uid"] == "uid-1"
    assert result["session"]


# ── registration ────────────────────────────────────────────────────────────

def test_registration_is_saved_before_the_email_is_verified(required, monkeypatch):
    """The profile is stored right after sign-up, before the user clicks the link."""
    monkeypatch.setattr(auth, "verify_firebase_token", lambda token: UNVERIFIED)
    conn = FakeConn(None)  # no existing profile
    body = auth.RegisterRequest(id_token="token", name="New User", email="user@example.com",
                                birthdate=date(2000, 1, 1))
    result = asyncio.run(auth.register(body, conn))
    assert result.status == "active"
    assert any("INSERT INTO users" in q for q in conn.queries)
