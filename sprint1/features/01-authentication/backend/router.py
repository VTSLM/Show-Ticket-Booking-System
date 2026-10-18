"""
router.py — FastAPI router for all authentication endpoints.

Prefix: /auth
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_current_user, require_role
from schemas import (
    ApproveUserRequest,
    ApproveUserResponse,
    ListPendingResponse,
    RegisterRequest,
    RegisterResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
import service

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Called after a successful Firebase sign-up. "
        "Customers are activated immediately; managers and admins require admin approval."
    ),
)
async def register(body: RegisterRequest) -> RegisterResponse:
    try:
        return await service.register_user(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/verify-token",
    response_model=VerifyTokenResponse,
    summary="Verify Firebase token and return user profile",
    description=(
        "Called on every app load / login. "
        "Returns user profile with role and the redirect path the frontend should use."
    ),
)
async def verify_token(body: VerifyTokenRequest) -> VerifyTokenResponse:
    try:
        return await service.verify_and_get_profile(body.firebase_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ---------------------------------------------------------------------------
# Protected: current user profile
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    summary="Get current user profile",
    description="Returns the authenticated user's profile. Requires a valid Firebase token.",
)
async def me(current_user: dict = Depends(get_current_user)) -> dict:
    from schemas import UserProfile
    from service import _redirect_for_roles

    roles: list[str] = list(current_user.get("roles") or [])
    return UserProfile(
        user_id=str(current_user["id"]),
        firebase_uid=current_user["firebase_uid"],
        name=current_user["name"],
        email=current_user["email"],
        phone=current_user.get("phone"),
        roles=roles,
        status=current_user["status"],
        redirect_to=_redirect_for_roles(roles),
    ).model_dump()


# ---------------------------------------------------------------------------
# Admin-only: pending approvals
# ---------------------------------------------------------------------------


@router.get(
    "/admin/pending",
    response_model=ListPendingResponse,
    summary="List users pending approval",
    description="Admin-only. Lists all users who registered as manager/admin and are awaiting activation.",
)
async def list_pending(
    _: dict = Depends(require_role("admin")),
) -> ListPendingResponse:
    pending = await service.list_pending_users()
    return ListPendingResponse(pending=pending)


@router.post(
    "/admin/pending/{user_id}",
    response_model=ApproveUserResponse,
    summary="Approve or reject a pending user",
    description=(
        "Admin-only. Set `action` to `approve` (activates the user) "
        "or `reject` (deletes the user and revokes their Firebase account)."
    ),
)
async def approve_user(
    user_id: str,
    body: ApproveUserRequest,
    _: dict = Depends(require_role("admin")),
) -> ApproveUserResponse:
    try:
        return await service.process_approval(user_id, body.action)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
