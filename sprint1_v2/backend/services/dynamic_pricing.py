"""
Dynamic seat pricing (Sprint 2, Tirth).

Managers switch dynamic pricing on or off per show (shows.dynamic_pricing).
When it is on, the price of each seat is its fixed base price (show_seats.price)
multiplied by a factor that depends on:

  - Demand        : how much of the show is already sold
  - Time to show  : last-minute surcharge; early-bird discount for live events
                    (concerts, theatre, other) — not movies, as cinemas don't do that
  - Time slot     : Friday–Sunday evening shows cost more (peak);
                    weekday movie shows before 5 PM are cheaper (off-peak)

The factor is always kept between MIN_MULTIPLIER and MAX_MULTIPLIER.
The price is frozen into show_seats.locked_price when a customer locks a seat,
so the amount shown at checkout never changes before payment.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple

MIN_MULTIPLIER = Decimal("0.80")
MAX_MULTIPLIER = Decimal("1.50")

# (sold fraction threshold, adjustment, label) — highest matching threshold wins
DEMAND_RULES = [
    (Decimal("0.80"), Decimal("0.25"), "High demand"),
    (Decimal("0.50"), Decimal("0.10"), "Filling fast"),
]
EARLY_BIRD_DAYS = 7
EARLY_BIRD_ADJUSTMENT = Decimal("-0.10")
EARLY_BIRD_EVENT_TYPES = {"concert", "theatre", "other"}   # live events only
OFF_PEAK_ADJUSTMENT = Decimal("-0.10")
OFF_PEAK_WEEKDAYS = {0, 1, 2, 3, 4}  # Monday–Friday
OFF_PEAK_BEFORE_HOUR = 17            # shows starting before 5 PM (India time)
OFF_PEAK_EVENT_TYPES = {"movie"}
LAST_MINUTE_HOURS = 24
LAST_MINUTE_ADJUSTMENT = Decimal("0.15")
PEAK_ADJUSTMENT = Decimal("0.10")
PEAK_WEEKDAYS = {4, 5, 6}          # Friday, Saturday, Sunday
PEAK_FROM_HOUR = 17                # 5 PM onwards (India time)
IST = timezone(timedelta(hours=5, minutes=30))


def compute_multiplier(
    start_time: datetime,
    sold_seats: int,
    total_seats: int,
    now: Optional[datetime] = None,
    event_type: Optional[str] = None,
) -> Tuple[Decimal, List[str]]:
    """Return (multiplier, reasons) for a show at this moment."""
    now = now or datetime.now(timezone.utc)
    event_type = (event_type or "movie").lower()
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    adjustment = Decimal("0")
    reasons: List[str] = []

    # 1. Demand
    if total_seats > 0:
        sold_fraction = Decimal(sold_seats) / Decimal(total_seats)
        for threshold, adj, label in DEMAND_RULES:
            if sold_fraction >= threshold:
                adjustment += adj
                reasons.append(label)
                break

    # 2. Time to show
    time_left = start_time - now
    if time_left > timedelta(days=EARLY_BIRD_DAYS):
        if event_type in EARLY_BIRD_EVENT_TYPES:
            adjustment += EARLY_BIRD_ADJUSTMENT
            reasons.append("Early-bird")
    elif timedelta(0) <= time_left <= timedelta(hours=LAST_MINUTE_HOURS):
        adjustment += LAST_MINUTE_ADJUSTMENT
        reasons.append("Last-minute")

    # 3. Time slot (India time): weekend evenings cost more, weekday daytime movies less
    local_start = start_time.astimezone(IST)
    if local_start.weekday() in PEAK_WEEKDAYS and local_start.hour >= PEAK_FROM_HOUR:
        adjustment += PEAK_ADJUSTMENT
        reasons.append("Peak time")
    elif (event_type in OFF_PEAK_EVENT_TYPES and local_start.weekday() in OFF_PEAK_WEEKDAYS
          and local_start.hour < OFF_PEAK_BEFORE_HOUR):
        adjustment += OFF_PEAK_ADJUSTMENT
        reasons.append("Off-peak")

    multiplier = min(MAX_MULTIPLIER, max(MIN_MULTIPLIER, Decimal("1") + adjustment))
    return multiplier, reasons


def apply_multiplier(base_price, multiplier: Decimal) -> Decimal:
    """Base price × multiplier, rounded to whole paise."""
    return (Decimal(str(base_price)) * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


NO_CHANGE = {"dynamic": False, "multiplier": Decimal("1"), "reasons": [], "change_pct": 0}


def pricing_summary(start_time: datetime, sold_seats: int, total_seats: int,
                    enabled: bool = True, event_type: Optional[str] = None) -> dict:
    """Multiplier, reasons and % change for a show — used by seat map and Browse."""
    if not enabled:
        return dict(NO_CHANGE)
    multiplier, reasons = compute_multiplier(start_time, sold_seats, total_seats, event_type=event_type)
    return {
        "dynamic": True,
        "multiplier": multiplier,
        "reasons": reasons,
        "change_pct": int(((multiplier - 1) * 100).to_integral_value(rounding=ROUND_HALF_UP)),
    }


async def get_show_pricing(conn, show_id: str) -> dict:
    """Current pricing of a show (multiplier 1 if dynamic pricing is off or the show does not exist)."""
    row = await conn.fetchrow(
        """SELECT sh.start_time, sh.dynamic_pricing, e.event_type::text AS event_type,
                  COUNT(ss.id)                                   AS total_seats,
                  COUNT(ss.id) FILTER (WHERE ss.status = 'booked') AS sold_seats
           FROM shows sh
           JOIN events e ON e.id = sh.event_id
           LEFT JOIN show_seats ss ON ss.show_id = sh.id
           WHERE sh.id = $1::uuid
           GROUP BY sh.id, e.event_type""",
        show_id,
    )
    if not row:
        return dict(NO_CHANGE)
    return pricing_summary(row["start_time"], row["sold_seats"], row["total_seats"],
                           row["dynamic_pricing"], row["event_type"])
