"""
Demo data for the Manager / Organizer analytics dashboard (Sprint 3, Tirth).

Adds realistic, CLEARLY LABELLED demo activity for EVERY published event of one approved
organization, so every chart, table and per-event view of the analytics dashboard has data:

  - 1500 demo customers      users.firebase_uid = 'demo-analytics-customer-NNNN',
                              email demo.customerNNNN@ticketflow.demo (they cannot log in)
  - past + upcoming shows    ~4 months of history plus upcoming shows for every event
  - bookings                 booking_number 'DEMO-…'  (confirmed, cancelled+refunded, expired)
  - payments                 transaction_id 'pay_DEMO…'
  - reviews and wishlists    written by the demo customers (each event has its own rating level)

Run from sprint3/backend (uses its .env database connection):
    venv/bin/python ../database/seeds/004_demo_manager_analytics.py            # add (skips if already there)
    venv/bin/python ../database/seeds/004_demo_manager_analytics.py --replace  # remove old demo data, add fresh
    venv/bin/python ../database/seeds/004_demo_manager_analytics.py --remove   # remove demo data only

Everything runs in one transaction: if anything fails, nothing is changed.
"""
import argparse
import asyncio
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(BACKEND, ".env"))

import asyncpg  # noqa: E402
from config import DATABASE_URL  # noqa: E402
from services.dynamic_pricing import compute_multiplier, apply_multiplier  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
DEMO_UID = "demo-analytics-customer-"
ORGANIZATION = "Skyline PVT LTD"
CUSTOMERS = 1500
RNG = random.Random(314)  # fixed seed → same demo data every time

REVIEWS = {
    "high": [
        ("Absolutely loved it", "One of the best shows I have been to this year. Would book again in a heartbeat."),
        ("A must-watch", "Brilliant from start to finish. Great seats and a smooth booking."),
        ("Worth every rupee", "Fantastic experience, the whole group enjoyed it."),
        ("Superb evening", "Great atmosphere, great sound, no complaints at all."),
        ("Totally recommend", "Booked last minute and it was totally worth it."),
    ],
    "mid": [
        ("Pretty good", "Enjoyable overall, a little long in the middle but worth it."),
        ("Nice outing", "Good show, the venue could improve the snacks queue."),
        ("Solid", "Did what it promised. Comfortable seats and on time."),
        ("Good, not great", "Liked most of it, a couple of slow parts."),
        ("Decent experience", "Fun time with friends, would go again for the right price."),
    ],
    "low": [
        ("Expected more", "It was okay, but the hype was bigger than the show."),
        ("Average", "Some good moments, but overall felt a bit flat."),
        ("Not for me", "The show was fine technically but did not really hold my interest."),
    ],
}


async def remove_demo(conn) -> dict:
    demo_users = [r["id"] for r in await conn.fetch(
        "SELECT id FROM users WHERE firebase_uid LIKE $1", DEMO_UID + "%")]
    demo_bookings = [r["id"] for r in await conn.fetch(
        "SELECT id FROM bookings WHERE booking_number LIKE 'DEMO-%'")]
    demo_shows = [r["show_id"] for r in await conn.fetch(
        """SELECT b.show_id FROM bookings b GROUP BY b.show_id
           HAVING bool_and(b.booking_number LIKE 'DEMO-%')""")]
    await conn.execute("DELETE FROM payments WHERE booking_id = ANY($1::uuid[])", demo_bookings)
    await conn.execute("DELETE FROM bookings WHERE id = ANY($1::uuid[])", demo_bookings)
    await conn.execute("DELETE FROM shows WHERE id = ANY($1::uuid[])", demo_shows)
    await conn.execute("DELETE FROM users WHERE id = ANY($1::uuid[])", demo_users)
    return {"users": len(demo_users), "bookings": len(demo_bookings), "shows": len(demo_shows)}


def build_plan(events, cinema, stadiums, today):
    """Which shows to create: (event, screen_id, start in IST, base price, dynamic, target occupancy).

    Every event gets past and upcoming shows, alternating DYNAMIC and FIXED pricing so the
    dashboard can compare the two for each event."""
    plan = []
    movie_hours = [10, 13, 16, 19, 21]
    for idx, e in enumerate(events):
        t = e["event_type"]
        popularity = RNG.uniform(0.55, 1.0)            # some events simply sell better
        flip = idx % 2                                 # which shows of this event start dynamic
        if t == "movie":
            days = sorted(RNG.sample(range(-118, -1), 12)) + sorted(RNG.sample(range(1, 26), 4))
            for k, day in enumerate(days):
                h = movie_hours[(k + idx) % len(movie_hours)]
                start = today + timedelta(days=day, hours=h, minutes=RNG.choice([0, 15, 30, 45]))
                peak = start.weekday() >= 4 and h >= 17
                occ = popularity * (RNG.uniform(0.8, 1.0) if peak else RNG.uniform(0.35, 0.8))
                plan.append((e, cinema, start, 250 if h >= 17 else 200, (k + flip) % 2 == 0,
                             occ if day < 0 else occ * RNG.uniform(0.25, 0.6)))
        elif t == "theatre":
            for k, day in enumerate(sorted(RNG.sample(range(-110, -1), 8)) + [6, 20]):
                start = today + timedelta(days=day, hours=RNG.choice([15, 19]))
                occ = popularity * RNG.uniform(0.55, 0.95)
                plan.append((e, cinema, start, 799, (k + flip) % 2 == 0, occ if day < 0 else occ * 0.4))
        elif t == "concert":
            screen = stadiums[idx % len(stadiums)]
            for k, day in enumerate(sorted(RNG.sample(range(-115, -10), 3)) + [RNG.randint(12, 28)]):
                start = today + timedelta(days=day, hours=19)
                occ = popularity * RNG.uniform(0.15, 0.3)
                plan.append((e, screen, start, RNG.choice([1500, 1800, 2200]), (k + flip) % 2 == 0,
                             occ if day < 0 else occ * 0.45))
        else:  # comedy / other
            for k, day in enumerate(sorted(RNG.sample(range(-112, -1), 8)) + [9, 23]):
                start = today + timedelta(days=day, hours=RNG.choice([18, 20, 21]))
                occ = popularity * RNG.uniform(0.5, 0.95)
                plan.append((e, cinema, start, 499, (k + flip) % 2 == 0, occ if day < 0 else occ * 0.35))
    return plan


async def seed(conn) -> dict:
    org = await conn.fetchrow(
        "SELECT id FROM organizer_profiles WHERE legal_name = $1 AND verification_status = 'APPROVED'",
        ORGANIZATION)
    if not org:
        raise SystemExit(f"Approved organization '{ORGANIZATION}' not found")

    events = [dict(r) for r in await conn.fetch(
        """SELECT id, title, event_type::text AS event_type FROM events
           WHERE organizer_id = $1 AND status = 'published' ORDER BY event_type, title, created_at""",
        org["id"])]
    screens = {(r["venue"], r["screen"]): r["id"] for r in await conn.fetch(
        """SELECT sc.id, v.name AS venue, sc.name AS screen FROM screens sc
           JOIN venues v ON v.id = sc.venue_id WHERE v.verification_status = 'approved'""")}
    cinema = screens.get(("PVR", "Screen 1"))
    stadiums = [sid for (v, _), sid in screens.items() if v == "Narendra Modi Stadium"]
    if not cinema or not stadiums:
        raise SystemExit("Approved screens 'PVR / Screen 1' and a 'Narendra Modi Stadium' screen are required")
    if not events:
        raise SystemExit("No published events found for the organization")

    now = datetime.now(timezone.utc)
    today = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    counts = {"events": len(events), "users": CUSTOMERS, "shows": 0, "bookings": 0,
              "confirmed": 0, "cancelled": 0, "expired": 0, "reviews": 0, "wishlists": 0}

    # ── demo customers: most book once or twice, a few are regulars; each has a favourite category ──
    users = [uuid.uuid4() for _ in range(CUSTOMERS)]
    activity = {u: 1 / (i + 1) ** 0.55 for i, u in enumerate(RNG.sample(users, len(users)))}
    favourite = {u: RNG.choices(["movie", "concert", "theatre", "other"], [62, 15, 10, 13])[0] for u in users}
    by_fav = {t: [u for u in users if favourite[u] == t] for t in ("movie", "concert", "theatre", "other")}

    def pick_user(event_type: str):
        pool = by_fav.get(event_type) if RNG.random() < 0.85 else None
        pool = pool or users
        return RNG.choices(pool, [activity[u] for u in pool])[0]

    event_buyers = {e["id"]: set() for e in events}
    await conn.executemany(
        """INSERT INTO users (id, firebase_uid, name, email, status, created_at)
           VALUES ($1, $2, $3, $4, 'active', $5)""",
        [(u, f"{DEMO_UID}{i:04d}", f"Demo Customer {i:04d}", f"demo.customer{i:04d}@ticketflow.demo",
          now - timedelta(days=RNG.randint(30, 200))) for i, u in enumerate(users, start=1)])
    await conn.execute(
        """INSERT INTO user_roles (user_id, role_id)
           SELECT u, r.id FROM unnest($1::uuid[]) AS u, roles r WHERE r.code = 'customer'
           ON CONFLICT DO NOTHING""", users)

    plan = build_plan(events, cinema, stadiums, today)

    for event, screen_id, start_ist, base, dynamic, target in plan:
        start = start_ist.astimezone(timezone.utc)
        past = start < now
        show_id = await conn.fetchval(
            """INSERT INTO shows (event_id, screen_id, start_time, end_time, base_price, status, dynamic_pricing)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id""",
            event["id"], screen_id, start, start + timedelta(hours=3), base,
            "completed" if past else "scheduled", dynamic)
        await conn.execute(
            """INSERT INTO show_seats (show_id, seat_id, price, status)
               SELECT $1, s.id, CASE WHEN s.seat_type = 'premium' THEN ROUND($2::numeric * 1.5, 2) ELSE $2::numeric END,
                      'available'
               FROM seats s WHERE s.screen_id = $3""",
            show_id, base, screen_id)
        seats = [dict(r) for r in await conn.fetch("SELECT id, price FROM show_seats WHERE show_id = $1", show_id)]
        RNG.shuffle(seats)
        counts["shows"] += 1

        # Sales happen in the 3 weeks before the show and never in the future
        sale_end = min(start - timedelta(hours=1), now - timedelta(minutes=30))
        sale_start = min(start - timedelta(days=21), sale_end - timedelta(days=21))
        span = (sale_end - sale_start).total_seconds()
        want, sold, pos, groups = int(len(seats) * min(target, 0.97)), 0, 0, []
        while pos < len(seats) and sold < want:
            n = RNG.choice([1, 2, 2, 2, 3, 4])
            group = seats[pos:pos + n]
            pos += n
            outcome = RNG.choices(["confirmed", "cancelled", "expired"], [82, 8, 10])[0]
            at = sale_start + timedelta(seconds=span * (RNG.random() ** 0.6))  # more sales near the show
            groups.append((at, group, outcome))
            if outcome == "confirmed":
                sold += len(group)
        groups.sort(key=lambda g: g[0])

        bookings, booking_seats, payments, booked_seat_ids = [], [], [], []
        sold_so_far = 0
        for at, group, outcome in groups:
            mult = compute_multiplier(start, sold_so_far, len(seats), now=at, event_type=event["event_type"])[0] \
                if dynamic else Decimal("1")
            prices = [apply_multiplier(s["price"], mult) for s in group]
            total = sum(prices)
            bid = uuid.uuid4()
            buyer = pick_user(event["event_type"])
            cancelled_at = min(at + timedelta(days=RNG.uniform(0.5, 4)), now) if outcome == "cancelled" else None
            bookings.append((bid, f"DEMO-{at.astimezone(IST):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
                             buyer, show_id, total, outcome,
                             at if outcome != "expired" else None, at, cancelled_at))
            booking_seats += [(bid, s["id"], p) for s, p in zip(group, prices)]
            counts["bookings"] += 1
            counts[outcome] += 1
            if outcome == "expired":
                continue
            paid_at = at + timedelta(minutes=RNG.randint(1, 6))
            if outcome == "confirmed":
                payments.append((bid, f"pay_DEMO{uuid.uuid4().hex[:10]}", total, "successful", paid_at,
                                 None, None, None))
                booked_seat_ids += [s["id"] for s in group]
                sold_so_far += len(group)
                event_buyers[event["id"]].add(buyer)
            else:
                payments.append((bid, f"pay_DEMO{uuid.uuid4().hex[:10]}", total, "refunded", paid_at,
                                 f"rfnd_DEMO{uuid.uuid4().hex[:10]}", total, cancelled_at))

        await conn.executemany(
            """INSERT INTO bookings (id, booking_number, user_id, show_id, total_amount, status, booked_at,
                                     created_at, updated_at, cancelled_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $8, $9)""", bookings)
        await conn.executemany(
            "INSERT INTO booking_seats (booking_id, show_seat_id, unit_price) VALUES ($1, $2, $3)", booking_seats)
        await conn.executemany(
            """INSERT INTO payments (booking_id, transaction_id, amount, currency, payment_method, status,
                                     paid_at, created_at, razorpay_refund_id, refunded_amount, refunded_at)
               VALUES ($1, $2, $3, 'INR', 'razorpay', $4::payment_status, $5, $5, $6, $7, $8)""", payments)
        await conn.execute(
            "UPDATE show_seats SET status = 'booked' WHERE id = ANY($1::uuid[])", booked_seat_ids)

    # ── reviews: written by people who actually bought tickets; every event has its own rating level ──
    reviews = []
    for e in events:
        quality = RNG.uniform(6.3, 9.3)
        reviewers = list(event_buyers[e["id"]]) or users
        for user in RNG.sample(reviewers, min(len(reviewers), RNG.randint(12, 30))):
            score = max(1, min(10, round(RNG.gauss(quality, 1.3))))
            head, text = RNG.choice(REVIEWS["high" if score >= 8 else "mid" if score >= 6 else "low"])
            when = now - timedelta(days=RNG.randint(1, 110), hours=RNG.randint(0, 23))
            reviews.append((e["id"], user, Decimal(score), head, text, when))
    await conn.executemany(
        """INSERT INTO reviews (event_id, user_id, rating, headline, content, is_draft, published_at, updated_at)
           VALUES ($1, $2, $3, $4, $5, false, $6, $6) ON CONFLICT (event_id, user_id) DO NOTHING""", reviews)
    counts["reviews"] = len(reviews)

    # ── wishlists ──
    wish = set()
    for user in RNG.sample(users, 600):
        for e in RNG.sample(events, RNG.randint(1, 3)):
            wish.add((user, e["id"]))
    await conn.executemany(
        """INSERT INTO wishlists (user_id, event_id, created_at) VALUES ($1, $2, $3)
           ON CONFLICT (user_id, event_id) DO NOTHING""",
        [(u, e, now - timedelta(days=RNG.randint(0, 100))) for u, e in wish])
    counts["wishlists"] = len(wish)
    return counts


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replace", action="store_true", help="remove existing demo data first")
    ap.add_argument("--remove", action="store_true", help="only remove demo data")
    args = ap.parse_args()

    conn = await asyncpg.connect(DATABASE_URL, ssl="require")
    try:
        async with conn.transaction():
            existing = await conn.fetchval("SELECT COUNT(*) FROM users WHERE firebase_uid LIKE $1", DEMO_UID + "%")
            if args.remove or args.replace:
                print("removed:", await remove_demo(conn))
                if args.remove:
                    return
            elif existing:
                print(f"Demo data already present ({existing} demo customers). Use --replace to rebuild it.")
                return
            print("added:", await seed(conn))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
