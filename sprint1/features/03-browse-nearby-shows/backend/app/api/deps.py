from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.repositories.location_repository import LocationRepository
from app.repositories.show_repository import ShowRepository
from app.services.location_service import LocationService
from app.services.show_service import ShowService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class Pagination:
    page: int = Query(1, ge=1, description="1-based page number")
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page"
    )


def get_show_service(session: SessionDep) -> ShowService:
    return ShowService(ShowRepository(session), settings)


def get_location_service(session: SessionDep) -> LocationService:
    return LocationService(LocationRepository(session))


ShowServiceDep = Annotated[ShowService, Depends(get_show_service)]
LocationServiceDep = Annotated[LocationService, Depends(get_location_service)]
PaginationDep = Annotated[Pagination, Depends()]
