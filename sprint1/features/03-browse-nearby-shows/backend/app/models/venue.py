import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SeatType
from app.models.mixins import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Venue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "venues"

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(10))


# Case-insensitive city lookups (used by "select location" + "nearby shows").
Index("ix_venues_city_lower", func.lower(Venue.city))


class Screen(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "screens"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(Integer)

    venue: Mapped[Venue] = relationship(lazy="raise")


class Seat(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "seats"
    __table_args__ = (UniqueConstraint("screen_id", "row_label", "seat_number"),)

    screen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("screens.id", ondelete="CASCADE"), index=True
    )
    row_label: Mapped[str] = mapped_column(String(5))
    seat_number: Mapped[int] = mapped_column(Integer)
    seat_type: Mapped[SeatType] = mapped_column(
        SAEnum(SeatType, name="seat_type"), default=SeatType.REGULAR, nullable=False
    )
