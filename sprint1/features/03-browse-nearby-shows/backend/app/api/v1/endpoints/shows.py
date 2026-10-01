import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import PaginationDep, ShowServiceDep
from app.models.enums import EventType
from app.schemas.common import Page
from app.schemas.show import ShowDetail, ShowListItem

router = APIRouter(prefix="/shows", tags=["Shows"])

CityQ = Annotated[str, Query(min_length=1, max_length=100, description="Selected city, e.g. Gandhinagar")]
OptCityQ = Annotated[str | None, Query(min_length=1, max_length=100)]
StateQ = Annotated[str | None, Query(max_length=100, description="Disambiguates same-named cities")]
TypeQ = Annotated[EventType | None, Query(description="Filter by event type")]
LangQ = Annotated[str | None, Query(max_length=50)]
GenreQ = Annotated[str | None, Query(max_length=100)]
DateFromQ = Annotated[date | None, Query(description="Earliest show date (inclusive)")]
DateToQ = Annotated[date | None, Query(description="Latest show date (inclusive)")]


@router.get("", response_model=Page[ShowListItem], summary="View nearby shows")
async def list_nearby_shows(
    service: ShowServiceDep,
    pagination: PaginationDep,
    city: CityQ,
    state: StateQ = None,
    event_type: TypeQ = None,
    language: LangQ = None,
    genre: GenreQ = None,
    date_from: DateFromQ = None,
    date_to: DateToQ = None,
):
    """Upcoming, bookable shows in the selected city, soonest first."""
    return await service.list_shows(
        city=city, state=state, event_type=event_type, language=language, genre=genre,
        date_from=date_from, date_to=date_to, page=pagination.page, page_size=pagination.page_size,
    )


@router.get("/search", response_model=Page[ShowListItem], summary="Search shows by name")
async def search_shows(
    service: ShowServiceDep,
    pagination: PaginationDep,
    q: Annotated[str, Query(min_length=1, max_length=200, description="Show / event name")],
    city: OptCityQ = None,
    state: StateQ = None,
    event_type: TypeQ = None,
    date_from: DateFromQ = None,
    date_to: DateToQ = None,
):
    """Case-insensitive partial match on the event title. Pass `city` to scope to a location."""
    return await service.list_shows(
        city=city, state=state, query=q, event_type=event_type,
        date_from=date_from, date_to=date_to, page=pagination.page, page_size=pagination.page_size,
    )


@router.get("/{show_id}", response_model=ShowDetail, summary="View show details")
async def get_show(show_id: uuid.UUID, service: ShowServiceDep):
    """Venue, date/time, per-seat-category pricing, availability and event info."""
    return await service.get_show_details(show_id)
