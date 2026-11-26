"""
Personalized recommendations, trending events and preferences (#218).

GET  /api/recommendations                     recommended + trending (login optional)
GET  /api/recommendations/trending            trending only (public)
POST /api/recommendations/views/{event_id}    count a view of an event page (login)
GET  /api/recommendations/preferences         the user's favourite genres, artists, cities
PUT  /api/recommendations/preferences         replace them
GET  /api/recommendations/preference-options  suggestions for the pickers (public)
"""
import uuid
from typing import List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user
from routers.reviews import get_optional_user, optional_security
from services import recommendations as rec
from services.geo_service import DEFAULT_RADIUS_KM

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class PreferencesBody(BaseModel):
    genres: List[str] = Field(default_factory=list, max_length=rec.MAX_PREFERENCE_ITEMS)
    artists: List[str] = Field(default_factory=list, max_length=rec.MAX_PREFERENCE_ITEMS)
    cities: List[str] = Field(default_factory=list, max_length=rec.MAX_PREFERENCE_ITEMS)


def _location(lat, lng, radius_km):
    # when called directly, unset Query() defaults are not numbers: treat them as "not sent"
    lat = lat if isinstance(lat, (int, float)) else None
    lng = lng if isinstance(lng, (int, float)) else None
    radius_km = radius_km if isinstance(radius_km, (int, float)) else DEFAULT_RADIUS_KM
    if (lat is None) != (lng is None):
        raise HTTPException(status_code=400, detail="Send both lat and lng")
    return lat, lng, radius_km


@router.get("")
async def get_recommendations(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0, le=500),
    auth: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    conn: asyncpg.Connection = Depends(get_conn),
):
    lat, lng, radius_km = _location(lat, lng, radius_km)
    user = await get_optional_user(auth, conn)
    return await rec.build(conn, user, lat, lng, radius_km)


@router.get("/trending")
async def get_trending(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lng: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(DEFAULT_RADIUS_KM, gt=0, le=500),
    conn: asyncpg.Connection = Depends(get_conn),
):
    lat, lng, radius_km = _location(lat, lng, radius_km)
    candidates = await rec.load_candidates(conn, lat, lng, radius_km)
    return {"trending": [rec.card(t) for t in await rec.trending(conn, candidates)]}


@router.post("/views/{event_id}")
async def record_event_view(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    try:
        uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Event not found")
    if not await rec.record_view(conn, current_user["id"], event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {"recorded": True}


@router.get("/preferences")
async def get_my_preferences(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await rec.get_preferences(conn, current_user["id"])


@router.put("/preferences")
async def update_my_preferences(
    body: PreferencesBody,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await rec.save_preferences(conn, current_user["id"], body.genres, body.artists,
                                      body.cities)


@router.get("/preference-options")
async def get_preference_options(conn: asyncpg.Connection = Depends(get_conn)):
    return await rec.preference_options(conn)
