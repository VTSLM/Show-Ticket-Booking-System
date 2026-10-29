from fastapi import APIRouter

from app.api.v1.endpoints import locations, shows

api_router = APIRouter()
api_router.include_router(locations.router)
api_router.include_router(shows.router)
