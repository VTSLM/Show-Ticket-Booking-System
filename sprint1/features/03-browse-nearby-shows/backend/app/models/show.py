import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ShowSeatStatus, ShowStatus
from app.models.event import Event
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.venue import Screen, Seat


class Show(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "shows"
    __table_args__ = (
        Index("ix_shows_status_start_time", "status", "start_time"),
        Index("ix_shows_screen_id_start_time", "screen_id", "start_time"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    screen_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("screens.id", ondelete="CASCADE")
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[ShowStatus] = mapped_column(
        SAEnum(ShowStatus, name="show_status"), default=ShowStatus.SCHEDULED, nullable=False
    )

    event: Mapped[Event] = relationship(lazy="raise")
    screen: Mapped[Screen] = relationship(lazy="raise")


class ShowSeat(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "show_seats"
    __table_args__ = (
        UniqueConstraint("show_id", "seat_id"),
        Index("ix_show_seats_show_id_status", "show_id", "status"),
    )

    show_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shows.id", ondelete="CASCADE")
    )
    seat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seats.id", ondelete="CASCADE")
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[ShowSeatStatus] = mapped_column(
        SAEnum(ShowSeatStatus, name="show_seat_status"),
        default=ShowSeatStatus.AVAILABLE,
        nullable=False,
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    seat: Mapped[Seat] = relationship(lazy="raise")
