from uuid import UUID
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from app.config import settings
from app.schemas.errors import AppAPIException, ErrorCode
from app.services.auth import get_current_user_id
from app.services.seat_service import simulate_booking_payment

router = APIRouter(prefix="/api/dev", tags=["Dev Payment Simulator"])


class SimulatePaymentResponse(BaseModel):
    success: bool
    message: str
    booking_id: str
    status: str


@router.post(
    "/simulate-payment/{booking_id}",
    response_model=SimulatePaymentResponse,
    summary="DEV ONLY: Simulate payment gateway confirmation"
)
async def post_simulate_payment(
    booking_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id)
):
    """
    LOCAL TESTING ONLY: Transitions a pending booking to confirmed and seats to booked.
    This endpoint is strictly disabled outside ENV=local.
    """
    if settings.ENV != "local" or not settings.ENABLE_DEV_PAYMENT_SIMULATOR:
        raise AppAPIException(
            status_code=403,
            code=ErrorCode.UNAUTHENTICATED,
            message="Payment simulator is disabled in this environment."
        )

    success = await simulate_booking_payment(booking_id, current_user_id)
    if not success:
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.HOLD_EXPIRED,
            message="Payment simulation failed: booking has expired or is not pending."
        )

    return SimulatePaymentResponse(
        success=True,
        message="Payment simulated successfully. Booking confirmed and seats marked booked.",
        booking_id=str(booking_id),
        status="confirmed"
    )
