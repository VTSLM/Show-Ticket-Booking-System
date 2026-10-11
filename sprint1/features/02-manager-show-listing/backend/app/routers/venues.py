from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import ManagerUser, get_current_manager
from app.database import fetch_all, fetch_one
from app.models import ScreenResponse, VenueResponse

router = APIRouter(prefix="/venues", tags=["Manager Venues"])

@router.get("", response_model=List[VenueResponse])
async def list_venues(
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Retrieve all venues and their screens.
    """
    venue_query = """
        SELECT id::text, name, address, city, state, pincode
        FROM venues
        ORDER BY name ASC;
    """
    venues = await fetch_all(venue_query)

    screen_query = """
        SELECT id::text, venue_id::text, name, capacity, created_at
        FROM screens
        ORDER BY name ASC;
    """
    screens = await fetch_all(screen_query)

    screens_by_venue = {}
    for s in screens:
        vid = s["venue_id"]
        screens_by_venue.setdefault(vid, []).append(ScreenResponse(**s))

    results = []
    for v in venues:
        v_dict = dict(v)
        v_dict["screens"] = screens_by_venue.get(v["id"], [])
        results.append(VenueResponse(**v_dict))

    return results

@router.get("/{venue_id}/screens", response_model=List[ScreenResponse])
async def list_venue_screens(
    venue_id: str,
    manager: ManagerUser = Depends(get_current_manager)
):
    """
    Retrieve screens belonging to a specific venue.
    """
    query = """
        SELECT id::text, venue_id::text, name, capacity, created_at
        FROM screens
        WHERE venue_id = $1::uuid
        ORDER BY name ASC;
    """
    screens = await fetch_all(query, venue_id)
    return screens
