"""Tests for firebase_admin_setup.verify_firebase_token and the auth dependency.

Firebase is never contacted: init_firebase is replaced and verify_id_token is mocked.
"""

import asyncio
import base64
import json

import firebase_admin
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import dependencies
import firebase_admin_setup


def _b64(data: dict) -> str:
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _forged_jwt(claims: dict) -> str:
    """A Firebase-shaped token whose signature was not made by Google."""
    signature = base64.urlsafe_b64encode(b"not-a-real-signature").decode().rstrip("=")
    return f"{_b64({'alg': 'RS256', 'kid': 'forged', 'typ': 'JWT'})}.{_b64(claims)}.{signature}"


@pytest.fixture
def firebase(monkeypatch):
    """Pretend Firebase Admin is initialised and record verify_id_token calls."""
    calls = []
    monkeypatch.setattr(firebase_admin_setup, "init_firebase", lambda: None)
    monkeypatch.setattr(firebase_admin, "_apps", {"[DEFAULT]": object()})

    def reject(token, **kwargs):
        calls.append(token)
        raise ValueError("Firebase rejected token")

    monkeypatch.setattr(firebase_admin_setup.firebase_auth, "verify_id_token", reject)
    return calls


def test_accepts_token_verified_by_firebase(firebase, monkeypatch):
    claims = {"uid": "firebase-user-1", "sub": "firebase-user-1", "email": "a@example.com"}
    monkeypatch.setattr(
        firebase_admin_setup.firebase_auth, "verify_id_token", lambda token, **kwargs: claims
    )

    assert firebase_admin_setup.verify_firebase_token("real-signed-token") == claims


@pytest.mark.parametrize("token", ["dev-some-admin-uid", "test-token", "valid-token"])
def test_rejects_former_development_tokens(firebase, token):
    with pytest.raises(ValueError):
        firebase_admin_setup.verify_firebase_token(token)
    assert firebase == [token]


def test_rejects_jwt_with_forged_signature(firebase):
    token = _forged_jwt({"user_id": "victim-uid", "sub": "victim-uid"})

    with pytest.raises(ValueError):
        firebase_admin_setup.verify_firebase_token(token)


def test_rejects_when_firebase_admin_is_not_initialised(monkeypatch):
    monkeypatch.setattr(firebase_admin_setup, "init_firebase", lambda: None)
    monkeypatch.setattr(firebase_admin, "_apps", {})

    with pytest.raises(ValueError):
        firebase_admin_setup.verify_firebase_token(_forged_jwt({"user_id": "victim-uid"}))


def test_rejects_verified_claims_without_uid(firebase, monkeypatch):
    monkeypatch.setattr(
        firebase_admin_setup.firebase_auth, "verify_id_token", lambda token, **kwargs: {}
    )

    with pytest.raises(ValueError):
        firebase_admin_setup.verify_firebase_token("token-without-uid")


@pytest.mark.parametrize("token", ["", None])
def test_rejects_empty_token(firebase, token):
    with pytest.raises(ValueError):
        firebase_admin_setup.verify_firebase_token(token)


@pytest.mark.parametrize(
    "token",
    ["dev-some-admin-uid", _forged_jwt({"user_id": "victim-uid", "sub": "victim-uid"})],
)
def test_auth_dependency_returns_401_for_unverified_tokens(firebase, token):
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(dependencies.get_current_firebase_uid(creds))

    assert exc.value.status_code == 401
