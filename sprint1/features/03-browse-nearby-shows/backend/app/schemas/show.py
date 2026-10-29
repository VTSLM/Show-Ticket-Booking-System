import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import EventType, SeatType, ShowStatus


class EventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    event_type: EventType
    duration_minutes: int | None = None
    language: str | None = None
    genre: str | None = None
    poster_url: str | None = None


class EventDetail(EventSummary):
    description: str | None = None


class VenueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str
    city: str
    state: str
    pincode: str


class ShowListItem(BaseModel):
    id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: ShowStatus
    event: EventSummary
    venue: VenueSummary
    screen_name: str
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    currency: str
    available_seats: int
    is_sold_out: bool


class SeatCategoryPricing(BaseModel):
    seat_type: SeatType
    min_price: Decimal
    max_price: Decimal
    available_seats: int
    total_seats: int


class ShowDetail(BaseModel):
    id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: ShowStatus
    event: EventDetail
    venue: VenueSummary
    screen_name: str
    currency: str
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    total_seats: int
    available_seats: int
    is_sold_out: bool
    seat_categories: list[SeatCategoryPricing]
