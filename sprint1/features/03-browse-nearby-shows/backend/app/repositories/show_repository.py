import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.enums import EventStatus, EventType, ShowSeatStatus, ShowStatus
from app.models.event import Event
from app.models.show import Show, ShowSeat
from app.models.venue import Screen, Seat, Venue


@dataclass(slots=True)
class ShowFilters:
    city: str | None = None
    state: str | None = None
    query: str | None = None
    event_type: EventType | None = None
    language: str | None = None
    genre: str | None = None
    start_from: datetime | None = None  # inclusive
    start_to: datetime | None = None  # exclusive


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _is_available_expr():
    """A seat is purchasable if AVAILABLE, or HELD with an expired lock."""
    return or_(
        ShowSeat.status == ShowSeatStatus.AVAILABLE,
        and_(ShowSeat.status == ShowSeatStatus.HELD, ShowSeat.locked_until < func.now()),
    )


class ShowRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------- query builders ----------
    @staticmethod
    def _join_base(stmt: Select) -> Select:
        return (
            stmt.select_from(Show)
            .join(Event, Event.id == Show.event_id)
            .join(Screen, Screen.id == Show.screen_id)
            .join(Venue, Venue.id == Screen.venue_id)
        )

    @staticmethod
    def _apply_filters(stmt: Select, f: ShowFilters) -> Select:
        # Only upcoming, bookable shows of published events are browsable.
        stmt = stmt.where(
            Show.status == ShowStatus.SCHEDULED,
            Event.status == EventStatus.PUBLISHED,
            Show.start_time > func.now(),
        )
        if f.city:
            stmt = stmt.where(func.lower(Venue.city) == f.city.strip().lower())
        if f.state:
            stmt = stmt.where(func.lower(Venue.state) == f.state.strip().lower())
        if f.query:
            stmt = stmt.where(Event.title.ilike(f"%{_escape_like(f.query.strip())}%", escape="!"))
        if f.event_type:
            stmt = stmt.where(Event.event_type == f.event_type)
        if f.language:
            stmt = stmt.where(func.lower(Event.language) == f.language.strip().lower())
        if f.genre:
            stmt = stmt.where(func.lower(Event.genre) == f.genre.strip().lower())
        if f.start_from:
            stmt = stmt.where(Show.start_time >= f.start_from)
        if f.start_to:
            stmt = stmt.where(Show.start_time < f.start_to)
        return stmt

    # ---------- public API ----------
    async def list_shows(self, f: ShowFilters, *, limit: int, offset: int):
        seats = (
            select(
                ShowSeat.show_id.label("show_id"),
                func.min(ShowSeat.price).label("min_price"),
                func.max(ShowSeat.price).label("max_price"),
                func.coalesce(func.sum(case((_is_available_expr(), 1), else_=0)), 0).label("available"),
            )
            .group_by(ShowSeat.show_id)
            .subquery()
        )

        stmt = self._join_base(
            select(Show, Event, Screen, Venue, seats.c.min_price, seats.c.max_price, seats.c.available)
        ).outerjoin(seats, seats.c.show_id == Show.id)
        stmt = (
            self._apply_filters(stmt, f)
            .order_by(Show.start_time.asc(), Show.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.execute(stmt)).all()

    async def count_shows(self, f: ShowFilters) -> int:
        stmt = self._apply_filters(self._join_base(select(func.count(Show.id))), f)
        return (await self.session.execute(stmt)).scalar_one()

    async def get_show_with_relations(self, show_id: uuid.UUID) -> Show | None:
        stmt = (
            select(Show)
            .where(Show.id == show_id)
            .options(joinedload(Show.event), joinedload(Show.screen).joinedload(Screen.venue))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_seat_category_stats(self, show_id: uuid.UUID):
        stmt = (
            select(
                Seat.seat_type,
                func.min(ShowSeat.price),
                func.max(ShowSeat.price),
                func.coalesce(func.sum(case((_is_available_expr(), 1), else_=0)), 0),
                func.count(ShowSeat.id),
            )
            .select_from(ShowSeat)
            .join(Seat, Seat.id == ShowSeat.seat_id)
            .where(ShowSeat.show_id == show_id)
            .group_by(Seat.seat_type)
            .order_by(func.min(ShowSeat.price))
        )
        return (await self.session.execute(stmt)).all()
