from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import ManagerUser, get_current_manager
from app.models import ShowCreateRequest, ShowHandoffResponse, ShowResponse
from app.services import show_service

router = APIRouter(prefix="/shows", tags=["Manager Shows"])

@router.get("", response_model=List[ShowResponse])
async def list_manager_shows(
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    List all scheduled shows for manager review.
    """
    return await show_service.list_shows()

@router.post("", response_model=ShowResponse, status_code=status.HTTP_201_CREATED)
async def create_show(
    show_data: ShowCreateRequest,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Schedule a new show for an event and screen in Supabase.
    Validates screen existence, event existence, time range, and scheduling conflicts.
    """
    return await show_service.create_show(show_data)

@router.get("/{show_id}", response_model=ShowResponse)
async def get_show(
    show_id: str,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Retrieve single show details.
    """
    show = await show_service.get_show_by_id(show_id)
    if not show:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Show with ID {show_id} not found."
        )
    return show

@router.get("/{show_id}/handoff", response_model=ShowHandoffResponse)
async def get_pricing_handoff(
    show_id: str,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Authoritative handoff endpoint for Feature 04 (Seat Selection & Pricing).
    Provides show metadata, screen ID, and validated physical seat count.
    """
    return await show_service.get_show_handoff(show_id)

@router.delete("/{show_id}")
async def delete_show(
    show_id: str,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Delete a scheduled show.
    """
    return await show_service.delete_show(show_id)
