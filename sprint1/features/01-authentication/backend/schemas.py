"""
schemas.py — Pydantic request / response models for the auth feature.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class StakeholderRole(str, Enum):
    customer = "customer"
    manager = "manager"
    admin = "admin"


class RegistrationStatus(str, Enum):
    active = "active"
    pending_approval = "pending_approval"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Sent by the frontend after Firebase sign-up succeeds."""

    firebase_token: Annotated[str, StringConstraints(min_length=1)]
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    requested_role: StakeholderRole = StakeholderRole.customer


class RegisterResponse(BaseModel):
    user_id: str
    name: str
    email: str
    role: str
    status: RegistrationStatus
    message: str


# ---------------------------------------------------------------------------
# Login / token verification
# ---------------------------------------------------------------------------


class VerifyTokenRequest(BaseModel):
    """Sent every time the user loads the app or logs in."""

    firebase_token: Annotated[str, StringConstraints(min_length=1)]


class UserProfile(BaseModel):
    user_id: str
    firebase_uid: str
    name: str
    email: str
    phone: str | None
    roles: list[str]
    status: str
    redirect_to: str  # frontend route the client should navigate to


class VerifyTokenResponse(BaseModel):
    user: UserProfile


# ---------------------------------------------------------------------------
# Admin: pending approvals
# ---------------------------------------------------------------------------


class PendingUser(BaseModel):
    user_id: str
    name: str
    email: str
    requested_role: str
    created_at: str


class ListPendingResponse(BaseModel):
    pending: list[PendingUser]


class ApprovalAction(str, Enum):
    approve = "approve"
    reject = "reject"


class ApproveUserRequest(BaseModel):
    action: ApprovalAction


class ApproveUserResponse(BaseModel):
    user_id: str
    action: ApprovalAction
    message: str
