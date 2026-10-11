from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

class EventTypeEnum(str, Enum):
    movie = "movie"
    concert = "concert"
    theatre = "theatre"
    other = "other"

class EventStatusEnum(str, Enum):
    draft = "draft"
    published = "published"
    inactive = "inactive"

class ShowStatusEnum(str, Enum):
    scheduled = "scheduled"
    cancelled = "cancelled"
    completed = "completed"

# Event Schemas
class EventCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Title of the movie/event")
    description: Optional[str] = Field(None, description="Event description or synopsis")
    event_type: EventTypeEnum = Field(..., description="Type of event: movie, concert, theatre, or other")
    duration_minutes: Optional[int] = Field(None, gt=0, description="Duration in minutes (must be positive)")
    language: Optional[str] = Field(None, max_length=50, description="Language of the event")
    genre: Optional[str] = Field(None, max_length=100, description="Genre of the event")
    poster_url: Optional[str] = Field(None, description="Cloudinary or CDN image URL for poster")
    status: EventStatusEnum = Field(default=EventStatusEnum.draft, description="Initial event status")

class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    event_type: str
    duration_minutes: Optional[int] = None
    language: Optional[str] = None
    genre: Optional[str] = None
    poster_url: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

# Venue & Screen Schemas
class ScreenCreateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Screen name, e.g. Screen 1, IMAX")
    capacity: int = Field(..., gt=0, description="Auditorium seating capacity (must be greater than 0)")

class ScreenResponse(BaseModel):
    id: str
    venue_id: str
    name: str
    capacity: int
    created_at: Optional[datetime] = None

class VenueCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, description="Cinema venue name")
    address: Optional[str] = Field(None, description="Address or Mall location")
    city: str = Field(..., min_length=2, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State")
    pincode: Optional[str] = Field(None, max_length=20, description="Postal / PIN code")
    screens: Optional[List[ScreenCreateInput]] = Field(default_factory=list, description="Initial screens to create")

class VenueResponse(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    city: str
    state: Optional[str] = None
    pincode: Optional[str] = None
    screens: Optional[List[ScreenResponse]] = None

class SeatCountInfo(BaseModel):
    screen_id: str
    screen_name: str
    venue_id: str
    venue_name: str
    seat_count: int
    source: str = Field(..., description="Source of the count: seats_table | layout_capacity | screen_capacity")
    screen_capacity: int
    seats_table_count: int
    layout_capacity: Optional[int] = None

# Show Schemas
class ShowCreateRequest(BaseModel):
    event_id: str = Field(..., description="UUID of the event")
    screen_id: str = Field(..., description="UUID of the screen")
    start_time: datetime = Field(..., description="Show start date and time with timezone")
    end_time: Optional[datetime] = Field(None, description="Show end date and time with timezone (must be after start_time)")

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v, info):
        if v is not None and "start_time" in info.data:
            if v <= info.data["start_time"]:
                raise ValueError("end_time must be strictly after start_time")
        return v

class ShowResponse(BaseModel):
    id: str
    event_id: str
    screen_id: str
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    updated_at: datetime
    # Enriched fields for manager view
    event_title: Optional[str] = None
    event_type: Optional[str] = None
    event_poster_url: Optional[str] = None
    venue_id: Optional[str] = None
    venue_name: Optional[str] = None
    screen_name: Optional[str] = None
    seat_count: Optional[int] = None
    pricing_ready: bool = Field(default=False, description="Whether teammate pricing has been completed")

class ShowHandoffResponse(BaseModel):
    show_id: str
    event_id: str
    event_title: str
    venue_id: str
    venue_name: str
    screen_id: str
    screen_name: str
    start_time: datetime
    end_time: datetime
    status: str
    seat_count: int
    pricing_ready: bool
    pricing_route: str
    integration_notes: str
