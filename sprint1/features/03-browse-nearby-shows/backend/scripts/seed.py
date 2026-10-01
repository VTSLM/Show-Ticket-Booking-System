"""Seed demo data:  python -m scripts.seed   (run after `alembic upgrade head`)"""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db.session import AsyncSessionLocal, engine
from app.models import Event, Screen, Seat, Show, ShowSeat, Venue
from app.models.enums import EventStatus, EventType, SeatType

VENUES = [
    ("Cinepolis Gandhinagar", "Sector 11, CH Road", "Gandhinagar", "Gujarat", "382011"),
    ("PVR Acropolis", "Thaltej, SG Highway", "Ahmedabad", "Gujarat", "380054"),
    ("INOX Phoenix", "Lower Parel", "Mumbai", "Maharashtra", "400013"),
]
EVENTS = [
    ("Interstellar Re-release", EventType.MOVIE, 169, "English", "Sci-Fi"),
    ("Stand-up Night Live", EventType.COMEDY, 90, "Hindi", "Comedy"),
    ("Garba Nights Concert", EventType.CONCERT, 150, "Gujarati", "Folk"),
]
PRICE = {SeatType.REGULAR: Decimal("200"), SeatType.PREMIUM: Decimal("350"), SeatType.RECLINER: Decimal("600")}


async def main() -> None:
    async with AsyncSessionLocal() as s:
        events = [
            Event(title=t, description=f"{t} - demo event", event_type=et, duration_minutes=d,
                  language=l, genre=g, status=EventStatus.PUBLISHED)
            for t, et, d, l, g in EVENTS
        ]
        s.add_all(events)
        base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(days=1)

        for name, addr, city, state, pin in VENUES:
            venue = Venue(name=name, address=addr, city=city, state=state, pincode=pin)
            screen = Screen(venue=venue, name="Screen 1", capacity=30)
            s.add_all([venue, screen])
            await s.flush()
            seats = []
            for row, stype in (("A", SeatType.REGULAR), ("B", SeatType.PREMIUM), ("C", SeatType.RECLINER)):
                for n in range(1, 11):
                    seats.append(Seat(screen_id=screen.id, row_label=row, seat_number=n, seat_type=stype))
            s.add_all(seats)
            await s.flush()
            for i, ev in enumerate(events):
                start = base + timedelta(hours=3 * i)
                show = Show(event_id=ev.id, screen_id=screen.id, start_time=start,
                            end_time=start + timedelta(minutes=ev.duration_minutes or 120))
                s.add(show)
                await s.flush()
                s.add_all([ShowSeat(show_id=show.id, seat_id=st.id, price=PRICE[st.seat_type]) for st in seats])
        await s.commit()
    await engine.dispose()
    print("Seeded.")


if __name__ == "__main__":
    asyncio.run(main())
