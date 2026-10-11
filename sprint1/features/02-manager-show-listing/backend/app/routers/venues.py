from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth import ManagerUser, get_current_manager
from app.database import fetch_all, fetch_one
from app.models import ScreenCreateInput, ScreenResponse, VenueCreateRequest, VenueResponse

router = APIRouter(prefix="/venues", tags=["Manager Venues"])

@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    request: VenueCreateRequest,
    manager: ManagerUser = Depends(get_current_manager),
):
    """
    Create a new cinema venue with optional initial auditorium screens.
    """
    insert_venue_query = """
        INSERT INTO venues (name, address, city, state, pincode)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id::text, name, address, city, state, pincode;
    """
    venue_row = await fetch_one(
        insert_venue_query,
        request.name.strip(),
        request.address.strip() if request.address else None,
        request.city.strip(),
        request.state.strip() if request.state else None,
        request.pincode.strip() if request.pincode else None,
    )
    if not venue_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create cinema venue."
        )

    venue_id = venue_row["id"]
    created_screens = []

    # Insert initial screens if provided
    if request.screens:
        for s in request.screens:
            insert_screen_query = """
                INSERT INTO screens (venue_id, name, capacity)
                VALUES ($1::uuid, $2, $3)
                RETURNING id::text, venue_id::text, name, capacity, created_at;
            """
            screen_row = await fetch_one(
                insert_screen_query,
                venue_id,
                s.name.strip(),
                s.capacity,
            )
            if screen_row:
                created_screens.append(ScreenResponse(**screen_row))

    result = dict(venue_row)
    result["screens"] = created_screens
    return VenueResponse(**result)

@router.post("/{venue_id}/screens", response_model=ScreenResponse, status_code=status.HTTP_201_CREATED)
async def create_venue_screen(
    venue_id: str,
    request: ScreenCreateInput,
    manager: ManagerUser = Depends(get_current_manager),
):
    """
    Add a screen/auditorium to an existing cinema venue.
    """
    venue_check = await fetch_one("SELECT id FROM venues WHERE id = $1::uuid;", venue_id)
    if not venue_check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue with id '{venue_id}' not found."
        )

    insert_screen_query = """
        INSERT INTO screens (venue_id, name, capacity)
        VALUES ($1::uuid, $2, $3)
        RETURNING id::text, venue_id::text, name, capacity, created_at;
    """
    try:
        screen_row = await fetch_one(
            insert_screen_query,
            venue_id,
            request.name.strip(),
            request.capacity,
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A screen named '{request.name}' already exists in this venue."
            )
        raise e

    if not screen_row:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create screen."
        )
    return ScreenResponse(**screen_row)

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
