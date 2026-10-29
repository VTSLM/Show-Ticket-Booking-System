from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, Response, status
from app.schemas.errors import AppAPIException, ErrorCode
from app.schemas.seat_selection import (
    SeatMapResponse,
    HoldCreateRequest,
    HoldCreateResponse,
    HoldDetailResponse,
    ReleaseResponse,
    HealthResponse
)
from app.services.auth import get_current_user_id, get_optional_user_id
from app.services.db import check_db_health
from app.services.seat_service import (
    get_seat_map_data,
    create_seat_hold,
    release_user_hold,
    get_hold_details
)

router = APIRouter(prefix="/api", tags=["Seat Selection"])


@router.get(
    "/shows/{show_id}/seat-map",
    response_model=SeatMapResponse,
    summary="Fetch seat map layout, show metadata, and caller's active hold"
)
async def get_seat_map(
    show_id: str,
    response: Response,
    if_none_match: Optional[str] = Header(None, alias="If-None-Match"),
    current_user_id: Optional[UUID] = Depends(get_optional_user_id)
):
    """
    Returns full seat map for a show. Auth is optional.
    If authenticated, marks caller's seats as is_mine=true and populates my_hold.
    Normalizes expired locks to available.
    Supports HTTP 304 via ETag / If-None-Match.
    In local dev with no DB, responds with a realistic in-memory demo map for any show ID.
    """
    try:
        show_uuid = UUID(show_id)
    except ValueError:
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=f"'{show_id}' is not a valid show ID. Show IDs must be UUID format (e.g. 11111111-1111-1111-1111-111111111111)."
        )

    map_data, etag = await get_seat_map_data(show_uuid, current_user_id)

    # ETag comparison for HTTP 304 Not Modified
    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return map_data



@router.post(
    "/shows/{show_id}/holds",
    response_model=HoldCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Atomically hold seats for a show"
)
async def post_seat_hold(
    show_id: UUID,
    req: HoldCreateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", description="Unique client UUID per hold attempt"),
    current_user_id: UUID = Depends(get_current_user_id)
):
    """
    Atomically locks seats and creates a pending booking.
    - Idempotency-Key guarantees safe retry without duplicate bookings.
    - Automatically cancels caller's prior pending hold on this show.
    - Returns 409 SEATS_UNAVAILABLE if any requested seat is unavailable.
    """
    if not idempotency_key or not idempotency_key.strip():
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Idempotency-Key header is required for seat hold operations."
        )

    try:
        seat_uuids = [UUID(s) for s in req.show_seat_ids]
    except ValueError:
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="One or more show_seat_ids are not valid UUID format."
        )

    return await create_seat_hold(
        show_id=show_id,
        user_id=current_user_id,
        show_seat_ids=seat_uuids,
        idempotency_key=idempotency_key.strip()
    )


@router.delete(
    "/holds/{booking_id}",
    response_model=ReleaseResponse,
    summary="Release active seat hold"
)
async def delete_hold(
    booking_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id)
):
    """
    Releases user's pending booking and unlocks all associated seats.
    Owner-only; another user's booking returns 404. Idempotent.
    """
    return await release_user_hold(booking_id, current_user_id)


@router.get(
    "/holds/{booking_id}",
    response_model=HoldDetailResponse,
    summary="Get hold state for checkout"
)
async def get_hold(
    booking_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id)
):
    """
    Fetches hold status for checkout transition.
    Owner-only; returns 404 for another user's hold.
    Returns 410 HOLD_EXPIRED if the hold window has elapsed.
    """
    return await get_hold_details(booking_id, current_user_id)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint for application and database status"
)
async def health_check():
    """Returns app and database connectivity health."""
    db_ok = await check_db_health()
    status_str = "ok" if db_ok else "degraded"
    http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE

    return Response(
        status_code=http_status,
        media_type="application/json",
        content=HealthResponse(
            status=status_str,
            app="ok",
            db="connected" if db_ok else "disconnected",
            timestamp=datetime.now(timezone.utc).isoformat()
        ).model_dump_json()
    )
