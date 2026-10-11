from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import ManagerUser, get_current_manager
from app.models import EventCreateRequest, EventResponse
from app.services import event_service

router = APIRouter(prefix="/events", tags=["Manager Events"])

@router.get("", response_model=List[EventResponse])
async def list_manager_events(
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Retrieve all events for manager dashboard.
    """
    return await event_service.list_events()

@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreateRequest,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Create a new movie or event in Supabase PostgreSQL database.
    """
    return await event_service.create_event(event_data)

@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Retrieve a specific event by ID.
    """
    event = await event_service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} not found."
        )
    return event
