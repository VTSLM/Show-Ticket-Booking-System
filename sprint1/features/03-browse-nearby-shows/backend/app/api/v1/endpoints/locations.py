from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import LocationServiceDep
from app.schemas.location import CityOut

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("/cities", response_model=list[CityOut], summary="List selectable cities")
async def list_cities(
    service: LocationServiceDep,
    q: Annotated[str | None, Query(min_length=1, max_length=100, description="City name prefix")] = None,
):
    """Cities that currently have upcoming shows. Powers the **Select Location** step."""
    return await service.list_cities(q)
