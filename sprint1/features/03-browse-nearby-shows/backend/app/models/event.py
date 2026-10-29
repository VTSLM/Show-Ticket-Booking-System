from sqlalchemy import Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import EventStatus, EventType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "events"

    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[EventType] = mapped_column(SAEnum(EventType, name="event_type"))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(50))
    genre: Mapped[str | None] = mapped_column(String(100))
    poster_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[EventStatus] = mapped_column(
        SAEnum(EventStatus, name="event_status"), default=EventStatus.DRAFT, nullable=False
    )
