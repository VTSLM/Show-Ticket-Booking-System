from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventStatus, ShowStatus
from app.models.event import Event
from app.models.show import Show
from app.models.venue import Screen, Venue


class LocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_cities(self, search: str | None = None):
        """Cities that currently have at least one upcoming bookable show."""
        stmt = (
            select(
                func.min(Venue.city).label("city"),
                func.min(Venue.state).label("state"),
                func.count(func.distinct(Show.id)).label("show_count"),
            )
            .select_from(Venue)
            .join(Screen, Screen.venue_id == Venue.id)
            .join(Show, Show.screen_id == Screen.id)
            .join(Event, Event.id == Show.event_id)
            .where(
                Show.status == ShowStatus.SCHEDULED,
                Event.status == EventStatus.PUBLISHED,
                Show.start_time > func.now(),
            )
            .group_by(func.lower(Venue.city), func.lower(Venue.state))
            .order_by(func.count(func.distinct(Show.id)).desc(), func.min(Venue.city))
        )
        if search:
            escaped = search.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
            stmt = stmt.where(Venue.city.ilike(f"{escaped}%", escape="!"))
        return (await self.session.execute(stmt)).all()
