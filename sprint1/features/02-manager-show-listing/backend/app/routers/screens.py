from fastapi import APIRouter, Depends
from app.auth import ManagerUser, get_current_manager
from app.models import SeatCountInfo
from app.services.seat_service import get_screen_seat_info

router = APIRouter(prefix="/screens", tags=["Manager Screens"])

@router.get("/{screen_id}/seat-count", response_model=SeatCountInfo)
async def get_seat_count(
    screen_id: str,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Retrieve authoritative seat count and breakdown for a screen.
    Used for show scheduling and handoff to the pricing module.
    """
    return await get_screen_seat_info(screen_id)
