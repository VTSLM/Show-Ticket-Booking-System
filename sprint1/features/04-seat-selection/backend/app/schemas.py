from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

class LayoutCreate(BaseModel):
    screen_id: Optional[UUID] = None
    screen_name: str = Field(min_length=1, max_length=120)
    rows: int = Field(gt=0, le=100)
    columns: int = Field(gt=0, le=100)
    approved_capacity: int = Field(ge=0)
    aisle_columns: list[int] = Field(default_factory=list)

class SeatUpdate(BaseModel):
    id: UUID
    row_index: int = Field(ge=0)
    col_index: int = Field(ge=0)
    label: str
    category: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    status: str = 'available'

class LayoutUpdate(BaseModel):
    screen_name: str = Field(min_length=1, max_length=120)
    approved_capacity: int = Field(ge=0)
    status: str = 'ready'
    seats: list[SeatUpdate]

class BulkUpdate(BaseModel):
    seat_ids: list[UUID] = Field(min_length=1)
    category: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[str] = None
