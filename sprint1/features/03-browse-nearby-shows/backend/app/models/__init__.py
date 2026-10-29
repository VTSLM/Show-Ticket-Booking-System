"""Import every model here so Alembic's autogenerate sees the full metadata."""
from app.models.booking import Booking, BookingSeat, Payment, Receipt
from app.models.event import Event
from app.models.show import Show, ShowSeat
from app.models.user import Role, User, UserRole
from app.models.venue import Screen, Seat, Venue

__all__ = [
    "Booking", "BookingSeat", "Payment", "Receipt", "Event", "Show", "ShowSeat",
    "Role", "User", "UserRole", "Screen", "Seat", "Venue",
]
