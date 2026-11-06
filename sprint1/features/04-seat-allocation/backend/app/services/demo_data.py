"""
Local demo seat map — used when ENV=local and no DATABASE_URL is configured.
Generates a realistic cinema with 6 sections, 200+ seats, varied statuses.
This is ONLY registered/reachable when the app boots without a DB in local mode.
"""
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.schemas.seat_selection import (
    SeatMapResponse,
    ShowDetails,
    ShowSeatItem,
    MyHoldSummary,
)

# Deterministic "show" ID for the demo  (constant so URLs stay stable)
DEMO_SHOW_ID = "11111111-1111-1111-1111-111111111111"

# Seat layout: (section_name, row_labels, seats_per_row, price, seat_type)
_SECTIONS = [
    ("PREMIUM",  ["A", "B"],           12, 699.0, "premium"),
    ("GOLD",     ["C", "D", "E"],      14, 499.0, "gold"),
    ("SILVER",   ["F", "G", "H", "I"], 16, 349.0, "silver"),
    ("CLASSIC",  ["J", "K", "L", "M", "N", "O"], 18, 199.0, "classic"),
]

# Deterministic seed for statuses — same seats show same status every boot
_STATUS_SEED = [
    # available=0, locked=1, booked=2, reserved=3
    0,0,0,0,0,0,0,0,0,0,0,0,  # mostly available in top rows
    0,0,0,2,2,0,0,0,2,0,0,0,0,0,
    0,0,2,2,2,2,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,2,2,2,0,0,0,0,0,1,1,  # two locked
    0,0,0,2,2,0,0,0,0,2,2,0,0,0,0,0,0,0,
    3,0,0,0,0,0,0,2,2,2,0,0,0,0,0,0,0,0,
]
_STATUS_MAP = ["available", "locked", "booked", "reserved"]


def _seat_uuid(row: str, num: int) -> str:
    """Deterministic UUID for a seat based on row + number."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"demo-seat-{row}-{num}"))


def build_demo_seat_map(
    current_user_id: Optional[str] = None,
    my_hold: Optional[MyHoldSummary] = None,
) -> SeatMapResponse:
    now_utc = datetime.now(timezone.utc)
    show_start = now_utc + timedelta(hours=3)

    show = ShowDetails(
        id=DEMO_SHOW_ID,
        title="Interstellar",
        language="English",
        genre="Sci-Fi / Drama",
        duration=169,
        poster_url="https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
        venue="PVR: Phoenix Palladium",
        city="Mumbai",
        screen="Audi 4 — Dolby Atmos",
        start_time=show_start.isoformat(),
        status="scheduled",
    )

    seats: list[ShowSeatItem] = []
    seed_idx = 0
    held_ids = set(my_hold.show_seat_ids) if my_hold else set()

    for _section, rows, seats_per_row, price, seat_type in _SECTIONS:
        for row in rows:
            for num in range(1, seats_per_row + 1):
                sid = _seat_uuid(row, num)
                seed_val = _STATUS_SEED[seed_idx % len(_STATUS_SEED)]
                seed_idx += 1

                if sid in held_ids:
                    status = "locked"
                    is_mine = True
                else:
                    status = _STATUS_MAP[seed_val]
                    is_mine = False

                seats.append(
                    ShowSeatItem(
                        show_seat_id=sid,
                        row_label=row,
                        seat_number=num,
                        seat_type=seat_type,
                        price=price,
                        status=status,
                        is_mine=is_mine,
                    )
                )

    # ETag: hash of seat statuses + user context
    hash_input = ";".join(f"{s.show_seat_id}:{s.status}:{s.is_mine}" for s in seats)
    user_str = current_user_id or "guest"
    etag_raw = f"{DEMO_SHOW_ID}:scheduled:{len(seats)}:{hashlib.md5(hash_input.encode()).hexdigest()}:{user_str}"
    etag = f'"{hashlib.sha256(etag_raw.encode()).hexdigest()[:16]}"'

    return SeatMapResponse(
        server_time=now_utc.isoformat(),
        show=show,
        max_seats_per_booking=8,
        bookable=True,
        bookable_reason=None,
        my_hold=my_hold,
        seats=seats,
    ), etag
