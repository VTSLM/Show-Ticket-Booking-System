from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ShowSeatItem(BaseModel):
    show_seat_id: str = Field(..., description="Unique show_seats record UUID")
    row_label: str = Field(..., description="Row identifier (e.g. A, B, AA)")
    seat_number: int = Field(..., description="Seat column index")
    seat_type: str = Field(..., description="Tier: standard | premium | accessible")
    price: float = Field(..., description="Seat ticket price in INR")
    status: str = Field(..., description="Display status: available | locked | booked | reserved")
    is_mine: bool = Field(default=False, description="True only if held by the requesting authenticated user")


class ShowDetails(BaseModel):
    id: str = Field(..., description="Show UUID")
    title: str = Field(..., description="Event or movie title")
    language: str = Field(..., description="Audio language")
    genre: str = Field(..., description="Genre classification")
    duration: int = Field(..., description="Duration in minutes")
    poster_url: Optional[str] = Field(None, description="Poster image URL")
    venue: str = Field(..., description="Cinema / venue name")
    city: str = Field(..., description="Venue city")
    screen: str = Field(..., description="Auditorium / screen name")
    start_time: str = Field(..., description="Show start time in ISO 8601 UTC")
    status: str = Field(..., description="Show lifecycle status: scheduled | cancelled | completed")


class MyHoldSummary(BaseModel):
    booking_id: str
    booking_number: str
    expires_at: str
    show_seat_ids: List[str]
    total_amount: float


class SeatMapResponse(BaseModel):
    server_time: str = Field(..., description="Server UTC timestamp in ISO 8601")
    show: ShowDetails
    max_seats_per_booking: int = Field(..., description="Max allowed seats per hold request")
    bookable: bool = Field(..., description="True if show is currently open for booking")
    bookable_reason: Optional[str] = Field(None, description="Explanation if show is not bookable")
    my_hold: Optional[MyHoldSummary] = Field(None, description="Active pending hold for the caller, or null")
    seats: List[ShowSeatItem] = Field(..., description="Flat list of seats in the auditorium")


class HoldCreateRequest(BaseModel):
    show_seat_ids: List[str] = Field(..., min_length=1, description="List of show_seat UUIDs to lock")

    @field_validator("show_seat_ids")
    @classmethod
    def validate_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Seat selection must contain at least one seat.")
        return v


class HoldCreateResponse(BaseModel):
    booking_id: str
    booking_number: str
    total_amount: float
    show_seat_ids: List[str]
    expires_at: str
    server_time: str


class HoldDetailResponse(BaseModel):
    booking_id: str
    booking_number: str
    show_id: str
    show_seat_ids: List[str]
    total_amount: float
    expires_at: str
    status: str
    server_time: str


class ReleaseResponse(BaseModel):
    success: bool
    message: str
    booking_id: str


class HealthResponse(BaseModel):
    status: str
    app: str
    db: str
    timestamp: str
