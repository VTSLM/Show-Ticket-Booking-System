import math
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.enums import EventStatus, EventType
from app.repositories.show_repository import ShowFilters, ShowRepository
from app.schemas.common import Page
from app.schemas.show import (
    EventDetail,
    EventSummary,
    SeatCategoryPricing,
    ShowDetail,
    ShowListItem,
    VenueSummary,
)


class ShowService:
    def __init__(self, repo: ShowRepository, settings: Settings):
        self.repo = repo
        self.settings = settings
        self.tz = ZoneInfo(settings.DEFAULT_TIMEZONE)

    async def list_shows(
        self,
        *,
        city: str | None = None,
        state: str | None = None,
        query: str | None = None,
        event_type: EventType | None = None,
        language: str | None = None,
        genre: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[ShowListItem]:
        if date_from and date_to and date_from > date_to:
            raise BadRequestError("date_from must be on or before date_to")

        filters = ShowFilters(
            city=city,
            state=state,
            query=query,
            event_type=event_type,
            language=language,
            genre=genre,
            # Interpret calendar dates in the business timezone, not UTC.
            start_from=datetime.combine(date_from, time.min, tzinfo=self.tz) if date_from else None,
            start_to=(
                datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=self.tz)
                if date_to
                else None
            ),
        )

        total = await self.repo.count_shows(filters)
        rows = await self.repo.list_shows(filters, limit=page_size, offset=(page - 1) * page_size)

        items = []
        for show, event, screen, venue, min_price, max_price, available in rows:
            available = int(available or 0)
            items.append(
                ShowListItem(
                    id=show.id,
                    start_time=show.start_time,
                    end_time=show.end_time,
                    status=show.status,
                    event=EventSummary.model_validate(event),
                    venue=VenueSummary.model_validate(venue),
                    screen_name=screen.name,
                    min_price=min_price,
                    max_price=max_price,
                    currency=self.settings.DEFAULT_CURRENCY,
                    available_seats=available,
                    is_sold_out=available == 0,
                )
            )

        return Page[ShowListItem](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_show_details(self, show_id: uuid.UUID) -> ShowDetail:
        show = await self.repo.get_show_with_relations(show_id)
        if show is None or show.event.status == EventStatus.DRAFT:
            raise NotFoundError("Show not found")

        stats = await self.repo.get_seat_category_stats(show_id)
        categories = [
            SeatCategoryPricing(
                seat_type=seat_type,
                min_price=min_p,
                max_price=max_p,
                available_seats=int(avail or 0),
                total_seats=total,
            )
            for seat_type, min_p, max_p, avail, total in stats
        ]
        total_seats = sum(c.total_seats for c in categories)
        available = sum(c.available_seats for c in categories)

        return ShowDetail(
            id=show.id,
            start_time=show.start_time,
            end_time=show.end_time,
            status=show.status,
            event=EventDetail.model_validate(show.event),
            venue=VenueSummary.model_validate(show.screen.venue),
            screen_name=show.screen.name,
            currency=self.settings.DEFAULT_CURRENCY,
            min_price=min((c.min_price for c in categories), default=None),
            max_price=max((c.max_price for c in categories), default=None),
            total_seats=total_seats,
            available_seats=available,
            is_sold_out=available == 0,
            seat_categories=categories,
        )
