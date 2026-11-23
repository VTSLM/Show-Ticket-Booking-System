"""
Manager / Organizer analytics: the calculations behind GET /api/manager/insights.

The router (routers/manager_analytics.py) checks the login and the inputs; everything here
only reads the database and builds the dashboard data.

Who sees what (``owner``):
  - a manager's own user id  -> only events of their organization(s) (organizer_profiles.user_id)
  - ``None`` (admin)          -> every organization's events

Counting rules (all dates in India time):
  - Revenue  = money from paid bookings (payments 'successful' or later 'refunded'),
               dated by payment time; refunds are subtracted on the refund date.
  - Tickets  = seats + standing-zone tickets of CONFIRMED bookings, dated by booking time.
  - Expired bookings are abandoned checkouts, never sales.
  - Occupancy / time slots / pricing comparison use shows that START in the period.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import asyncpg

IST = timezone(timedelta(hours=5, minutes=30))
TZ = "Asia/Kolkata"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SLOTS = [("morning", "Morning (before 12)"), ("afternoon", "Afternoon (12–5)"),
         ("evening", "Evening (5–9)"), ("night", "Night (after 9)")]

# Events this caller may see ($1 = owner user id or NULL for admin, $2 = event id or NULL)
MY_EVENTS = """
    my_events AS (
        SELECT e.id, e.title, e.event_type::text AS event_type
        FROM events e
        LEFT JOIN organizer_profiles op ON op.id = e.organizer_id   -- admins also see events without an organization
        WHERE ($1::uuid IS NULL OR op.user_id = $1::uuid)
          AND ($2::uuid IS NULL OR e.id = $2::uuid)
    )"""

# Ticket count of a booking: reserved seats + standing-zone quantity
TICKETS = """(
    (SELECT COUNT(*) FROM booking_seats bs WHERE bs.booking_id = b.id)
    + COALESCE((SELECT SUM(bz.quantity) FROM booking_zones bz WHERE bz.booking_id = b.id), 0)
)"""


def _f(x) -> float:
    return float(x or 0)


def _pct_change(now: float, before: float) -> Optional[float]:
    if before == 0:
        return None
    return round((now - before) / before * 100, 1)


def resolve_range(days: int, start: Optional[date], end: Optional[date],
                  today: Optional[date] = None) -> tuple[date, date]:
    """Date window for the dashboard: the last ``days`` days, or an explicit start/end.

    Raises ValueError with a user-facing message for an invalid custom range.
    """
    today = today or datetime.now(IST).date()
    if start or end:
        if not (start and end):
            raise ValueError("Give both start and end dates")
        if end < start:
            raise ValueError("End date must be on or after start date")
        if (end - start).days > 730:
            raise ValueError("Date range can be at most 2 years")
        return start, end
    return today - timedelta(days=days - 1), today


async def build_overview(conn: asyncpg.Connection, owner: Optional[str], event_id: Optional[str],
                         d_from: date, d_to: date, has_org: bool = True) -> dict:
    """Everything the dashboard shows for one period (and optionally one event)."""
    span = (d_to - d_from).days + 1
    p_from, p_to = d_from - timedelta(days=span), d_from - timedelta(days=1)
    is_admin = owner is None

    base = (owner, event_id)

    # ── Events the caller can choose in the filter ──
    events = await conn.fetch(
        f"WITH {MY_EVENTS} SELECT id, title, event_type FROM my_events ORDER BY title",
        owner, None,
    )

    # ── Revenue & tickets for a date window ──
    async def money_and_tickets(a: date, b: date):
        rev = await conn.fetchrow(
            f"""WITH {MY_EVENTS}
                SELECT
                  COALESCE(SUM(p.amount) FILTER (WHERE
                      (COALESCE(p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4), 0) AS gross,
                  COALESCE(SUM(p.refunded_amount) FILTER (WHERE p.refunded_amount IS NOT NULL AND
                      (COALESCE(p.refunded_at, p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4), 0) AS refunds
                FROM payments p
                JOIN bookings b ON b.id = p.booking_id
                JOIN shows s ON s.id = b.show_id
                JOIN my_events me ON me.id = s.event_id
                WHERE p.status IN ('successful', 'refunded')""",
            *base, a, b,
        )
        tix = await conn.fetchrow(
            f"""WITH {MY_EVENTS}
                SELECT COUNT(*) AS bookings, COALESCE(SUM({TICKETS}), 0) AS tickets,
                       COALESCE(SUM(b.total_amount), 0) AS amount, COUNT(DISTINCT b.user_id) AS buyers
                FROM bookings b
                JOIN shows s ON s.id = b.show_id
                JOIN my_events me ON me.id = s.event_id
                WHERE b.status = 'confirmed'
                  AND (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4""",
            *base, a, b,
        )
        return rev, tix

    rev, tix = await money_and_tickets(d_from, d_to)
    prev_rev, prev_tix = await money_and_tickets(p_from, p_to)
    net = _f(rev["gross"]) - _f(rev["refunds"])
    prev_net = _f(prev_rev["gross"]) - _f(prev_rev["refunds"])

    # ── Booking outcomes (bookings started in the period) ──
    outcome_rows = await conn.fetch(
        f"""WITH {MY_EVENTS}
            SELECT b.status::text AS status, COUNT(*) AS n
            FROM bookings b
            JOIN shows s ON s.id = b.show_id
            JOIN my_events me ON me.id = s.event_id
            WHERE (b.created_at AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4
            GROUP BY 1""",
        *base, d_from, d_to,
    )
    outcomes = {s: 0 for s in ("confirmed", "pending", "expired", "cancelled")}
    for r in outcome_rows:
        outcomes[r["status"]] = r["n"]
    cancelled_in_period = await conn.fetchval(
        f"""WITH {MY_EVENTS}
            SELECT COUNT(*) FROM bookings b
            JOIN shows s ON s.id = b.show_id JOIN my_events me ON me.id = s.event_id
            WHERE b.status = 'cancelled'
              AND (COALESCE(b.cancelled_at, b.updated_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4""",
        *base, d_from, d_to,
    )
    decided = outcomes["confirmed"] + outcomes["cancelled"]
    prev_outcomes = {s_: 0 for s_ in ("confirmed", "pending", "expired", "cancelled")}
    for r in await conn.fetch(
        f"""WITH {MY_EVENTS}
            SELECT b.status::text AS status, COUNT(*) AS n
            FROM bookings b JOIN shows s ON s.id = b.show_id JOIN my_events me ON me.id = s.event_id
            WHERE (b.created_at AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4 GROUP BY 1""",
        *base, p_from, p_to,
    ):
        prev_outcomes[r["status"]] = r["n"]

    # ── Per-show capacity & sales for shows starting in the period ──
    show_rows = await conn.fetch(
        f"""WITH {MY_EVENTS},
            seat_cap AS (
                SELECT ss.show_id, COUNT(*) AS cap, COUNT(*) FILTER (WHERE ss.status = 'booked') AS sold
                FROM show_seats ss GROUP BY ss.show_id
            ),
            zone_cap AS (
                SELECT z.show_id, SUM(z.total_capacity) AS cap, SUM(z.booked_count) AS sold
                FROM show_zones z GROUP BY z.show_id
            ),
            show_money AS (
                SELECT b.show_id,
                       SUM(p.amount - COALESCE(p.refunded_amount, 0)) AS revenue
                FROM payments p JOIN bookings b ON b.id = p.booking_id
                WHERE p.status IN ('successful', 'refunded')
                GROUP BY b.show_id
            ),
            show_tix AS (
                SELECT b.show_id, SUM({TICKETS}) AS tickets
                FROM bookings b WHERE b.status = 'confirmed' GROUP BY b.show_id
            )
            SELECT s.id, s.start_time, s.status::text AS status, s.dynamic_pricing, s.base_price,
                   me.id AS event_id, me.title, me.event_type, v.name AS venue, sc.name AS screen,
                   COALESCE(sc_.cap, 0) + COALESCE(zc.cap, 0) AS capacity,
                   COALESCE(sc_.sold, 0) + COALESCE(zc.sold, 0) AS sold,
                   COALESCE(sm.revenue, 0) AS revenue,
                   COALESCE(st.tickets, 0) AS tickets
            FROM shows s
            JOIN my_events me ON me.id = s.event_id
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            LEFT JOIN seat_cap sc_ ON sc_.show_id = s.id
            LEFT JOIN zone_cap zc ON zc.show_id = s.id
            LEFT JOIN show_money sm ON sm.show_id = s.id
            LEFT JOIN show_tix st ON st.show_id = s.id
            WHERE s.status <> 'cancelled'
              AND ((s.start_time AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4 OR s.start_time > now())""",
        *base, d_from, d_to,
    )
    now = datetime.now(timezone.utc)
    in_period = [r for r in show_rows if d_from <= r["start_time"].astimezone(IST).date() <= d_to]
    cap_total = sum(r["capacity"] for r in in_period)
    sold_total = sum(r["sold"] for r in in_period)

    upcoming = sorted((r for r in show_rows if r["start_time"] > now), key=lambda r: r["start_time"])[:12]

    # ── Best days / time slots (shows starting in the period) ──
    weekday = [{"day": d, "tickets": 0, "revenue": 0.0} for d in WEEKDAYS]
    slot_map = {k: {"slot": label, "tickets": 0, "revenue": 0.0} for k, label in SLOTS}
    for r in in_period:
        local = r["start_time"].astimezone(IST)
        weekday[local.weekday()]["tickets"] += int(r["tickets"])
        weekday[local.weekday()]["revenue"] += _f(r["revenue"])
        h = local.hour
        key = "morning" if h < 12 else "afternoon" if h < 17 else "evening" if h < 21 else "night"
        slot_map[key]["tickets"] += int(r["tickets"])
        slot_map[key]["revenue"] += _f(r["revenue"])

    # ── Dynamic vs fixed pricing (shows starting in the period) ──
    def group(rows):
        cap = sum(r["capacity"] for r in rows)
        tickets = sum(int(r["tickets"]) for r in rows)
        revenue = sum(_f(r["revenue"]) for r in rows)
        return {
            "shows": len(rows),
            "tickets": tickets,
            "revenue": round(revenue, 2),
            "occupancy": round(sum(r["sold"] for r in rows) / cap * 100, 1) if cap else 0.0,
            "avg_ticket_price": round(revenue / tickets, 2) if tickets else 0.0,
        }
    pricing = {
        "dynamic": group([r for r in in_period if r["dynamic_pricing"]]),
        "fixed": group([r for r in in_period if not r["dynamic_pricing"]]),
    }

    # ── Revenue trend (one point per day) ──
    rev_days = await conn.fetch(
        f"""WITH {MY_EVENTS}
            SELECT d::date AS day,
                   COALESCE(SUM(p.amount) FILTER (WHERE (COALESCE(p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date = d::date), 0)
                 - COALESCE(SUM(p.refunded_amount) FILTER (WHERE p.refunded_amount IS NOT NULL AND
                       (COALESCE(p.refunded_at, p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date = d::date), 0) AS revenue
            FROM generate_series($3::date, $4::date, interval '1 day') d
            LEFT JOIN (payments p
                       JOIN bookings b ON b.id = p.booking_id
                       JOIN shows s ON s.id = b.show_id
                       JOIN my_events me ON me.id = s.event_id)
              ON p.status IN ('successful', 'refunded')
             AND ((COALESCE(p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date = d::date
                  OR (COALESCE(p.refunded_at, p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date = d::date)
            GROUP BY d ORDER BY d""",
        *base, d_from, d_to,
    )
    tix_days = await conn.fetch(
        f"""WITH {MY_EVENTS}
            SELECT (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date AS day, SUM({TICKETS}) AS tickets
            FROM bookings b JOIN shows s ON s.id = b.show_id JOIN my_events me ON me.id = s.event_id
            WHERE b.status = 'confirmed'
              AND (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4
            GROUP BY 1""",
        *base, d_from, d_to,
    )
    tix_by_day = {r["day"]: int(r["tickets"]) for r in tix_days}
    trend = [{"date": r["day"].isoformat(), "revenue": round(_f(r["revenue"]), 2),
              "tickets": tix_by_day.get(r["day"], 0)} for r in rev_days]

    # ── Per-event table ──
    ev_rows = await conn.fetch(
        f"""WITH {MY_EVENTS}
            SELECT me.id, me.title, me.event_type,
              (SELECT COALESCE(SUM(p.amount), 0) FROM payments p JOIN bookings b ON b.id = p.booking_id
                 JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = me.id AND p.status IN ('successful', 'refunded')
                  AND (COALESCE(p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4)
            - (SELECT COALESCE(SUM(p.refunded_amount), 0) FROM payments p JOIN bookings b ON b.id = p.booking_id
                 JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = me.id AND p.refunded_amount IS NOT NULL
                  AND (COALESCE(p.refunded_at, p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4) AS revenue,
              (SELECT COALESCE(SUM(p.amount), 0) FROM payments p JOIN bookings b ON b.id = p.booking_id
                 JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = me.id AND p.status IN ('successful', 'refunded')
                  AND (COALESCE(p.paid_at, p.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4) AS gross,
              (SELECT COALESCE(SUM(b.total_amount), 0) FROM bookings b JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = me.id AND b.status = 'confirmed'
                  AND (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4) AS paid,
              (SELECT COALESCE(SUM({TICKETS}), 0) FROM bookings b JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = me.id AND b.status = 'confirmed'
                  AND (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4) AS tickets,
              (SELECT ROUND(AVG(r.rating)::numeric, 1) FROM reviews r
                WHERE r.event_id = me.id AND COALESCE(r.is_draft, false) = false) AS rating,
              (SELECT COUNT(*) FROM reviews r WHERE r.event_id = me.id AND COALESCE(r.is_draft, false) = false) AS reviews,
              (SELECT COUNT(*) FROM wishlists w WHERE w.event_id = me.id) AS wishlisted
            FROM my_events me""",
        *base, d_from, d_to,
    )
    shows_by_event = {}
    for r in in_period:
        e = shows_by_event.setdefault(r["event_id"], {"shows": 0, "cap": 0, "sold": 0})
        e["shows"] += 1
        e["cap"] += r["capacity"]
        e["sold"] += r["sold"]
    by_event = []
    for r in ev_rows:
        s = shows_by_event.get(r["id"], {"shows": 0, "cap": 0, "sold": 0})
        row = {
            "event_id": str(r["id"]), "title": r["title"], "event_type": r["event_type"],
            "revenue": round(_f(r["revenue"]), 2), "gross_revenue": round(_f(r["gross"]), 2),
            "tickets": int(r["tickets"]),
            "avg_ticket_price": round(_f(r["paid"]) / int(r["tickets"]), 2) if int(r["tickets"]) else None,
            "shows": s["shows"], "occupancy": round(s["sold"] / s["cap"] * 100, 1) if s["cap"] else None,
            "rating": _f(r["rating"]) if r["rating"] is not None else None,
            "reviews": r["reviews"], "wishlisted": r["wishlisted"],
        }
        if row["revenue"] or row["tickets"] or row["shows"] or row["wishlisted"] or row["reviews"]:
            by_event.append(row)
    by_event.sort(key=lambda x: (-x["revenue"], -x["tickets"], x["title"]))

    # ── All-time audience signals ──
    rating = await conn.fetchrow(
        f"""WITH {MY_EVENTS}
            SELECT ROUND(AVG(r.rating)::numeric, 1) AS avg, COUNT(*) AS n
            FROM reviews r JOIN my_events me ON me.id = r.event_id
            WHERE COALESCE(r.is_draft, false) = false""",
        *base,
    )
    wishlisted = await conn.fetchval(
        f"WITH {MY_EVENTS} SELECT COUNT(*) FROM wishlists w JOIN my_events me ON me.id = w.event_id", *base)

    tickets = int(tix["tickets"])

    # ── (2) Booking lead time: how many days before the show people book ──
    lead_rows = await conn.fetch(
        f"""WITH {MY_EVENTS}
            SELECT GREATEST(0, EXTRACT(EPOCH FROM (s.start_time - COALESCE(b.booked_at, b.created_at))) / 86400.0) AS days,
                   {TICKETS} AS t
            FROM bookings b JOIN shows s ON s.id = b.show_id JOIN my_events me ON me.id = s.event_id
            WHERE b.status = 'confirmed'
              AND (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date BETWEEN $3 AND $4""",
        *base, d_from, d_to,
    )
    buckets = [("Same day", 0, 1), ("1–2 days", 1, 3), ("3–7 days", 3, 8), ("8–14 days", 8, 15), ("15+ days", 15, 10 ** 6)]
    lead_buckets = [{"label": lbl, "bookings": 0, "tickets": 0} for lbl, _, _ in buckets]
    lead_days = []
    for r in lead_rows:
        dd = float(r["days"])
        lead_days.append(dd)
        for i, (_, lo, hi) in enumerate(buckets):
            if lo <= dd < hi:
                lead_buckets[i]["bookings"] += 1
                lead_buckets[i]["tickets"] += int(r["t"])
                break
    lead_days.sort()
    avg_lead = round(sum(lead_days) / len(lead_days), 1) if lead_days else None
    median_lead = round(lead_days[len(lead_days) // 2], 1) if lead_days else None

    # ── (2) Sales curve: % of a show's tickets already sold N days before it (shows already played) ──
    played_ids = [r["id"] for r in in_period if r["start_time"] <= now]
    curve_rows = await conn.fetch(
        f"""SELECT GREATEST(0, EXTRACT(EPOCH FROM (s.start_time - COALESCE(b.booked_at, b.created_at))) / 86400.0) AS days,
                   {TICKETS} AS t
            FROM bookings b JOIN shows s ON s.id = b.show_id
            WHERE b.status = 'confirmed' AND b.show_id = ANY($1::uuid[])""",
        played_ids,
    ) if played_ids else []
    curve_total = sum(int(r["t"]) for r in curve_rows)
    sales_curve = [{
        "days_before": d,
        "pct_sold": round(sum(int(r["t"]) for r in curve_rows if float(r["days"]) >= d) / curve_total * 100, 1) if curve_total else 0.0,
    } for d in (21, 14, 10, 7, 5, 3, 2, 1, 0)]

    # ── (6) Customers: new vs returning, repeat buyers, cross-category ──
    cust_rows = await conn.fetch(
        f"""WITH {MY_EVENTS},
            conf AS (
                SELECT b.user_id, (COALESCE(b.booked_at, b.created_at) AT TIME ZONE '{TZ}')::date AS d, me.event_type
                FROM bookings b JOIN shows s ON s.id = b.show_id JOIN my_events me ON me.id = s.event_id
                WHERE b.status = 'confirmed'
            )
            SELECT user_id,
                   MIN(d) AS first_day,
                   COUNT(*) FILTER (WHERE d BETWEEN $3 AND $4) AS in_period,
                   COUNT(*) FILTER (WHERE d < $3) AS before_period,
                   ARRAY_AGG(DISTINCT event_type) AS types
            FROM conf GROUP BY user_id
            HAVING COUNT(*) FILTER (WHERE d BETWEEN $3 AND $4) > 0""",
        *base, d_from, d_to,
    )
    combos: dict = {}
    for r in cust_rows:
        types = sorted(t for t in (r["types"] or []) if t)
        if len(types) >= 2:
            key = " + ".join(t.capitalize() for t in types)
            combos[key] = combos.get(key, 0) + 1
    buyers_n = len(cust_rows)
    new_n = sum(1 for r in cust_rows if r["first_day"] >= d_from)
    repeat_n = sum(1 for r in cust_rows if r["in_period"] >= 2)
    cross_n = sum(combos.values())
    customers = {
        "buyers": buyers_n,
        "new": new_n,
        "returning": buyers_n - new_n,
        "repeat_buyers": repeat_n,
        "repeat_rate_pct": round(repeat_n / buyers_n * 100, 1) if buyers_n else 0.0,
        "cross_category": cross_n,
        "cross_category_pct": round(cross_n / buyers_n * 100, 1) if buyers_n else 0.0,
        "top_combos": [{"combo": k, "customers": v} for k, v in sorted(combos.items(), key=lambda x: -x[1])[:5]],
    }

    # ── (8) Smart alerts ──
    alerts = []
    def alert(level, text):
        alerts.append({"level": level, "text": text})
    hot, slow = [], []
    for u in sorted(upcoming, key=lambda r: r["start_time"]):
        occ = u["sold"] / u["capacity"] * 100 if u["capacity"] else 0
        when = u["start_time"].astimezone(IST).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
        hours_left = (u["start_time"] - now).total_seconds() / 3600
        if occ >= 80:
            tip = "" if u["dynamic_pricing"] else " Consider turning on dynamic pricing or adding a show."
            hot.append(f"🔥 {u['title']} on {when} is {round(occ)}% sold.{tip}")
        elif hours_left <= 72 and u["capacity"] and occ < 25:
            slow.append((occ, f"⚠️ {u['title']} on {when} starts within 3 days but is only {round(occ)}% sold."))
    for text in hot[:2]:
        alert("good", text)
    if len(hot) > 2:
        alert("good", f"🔥 {len(hot) - 2} more upcoming show(s) are over 80% sold.")
    for _, text in sorted(slow)[:2]:          # the two weakest first
        alert("warn", text)
    if len(slow) > 2:
        alert("warn", f"⚠️ {len(slow) - 2} more show(s) in the next 3 days are under 25% sold.")
    rc = _pct_change(net, prev_net)
    if rc is not None and abs(rc) >= 20:
        alert("good" if rc > 0 else "warn",
              f"{'📈' if rc > 0 else '📉'} Revenue is {'up' if rc > 0 else 'down'} {abs(rc)}% compared with the previous {span} days.")
    prev_decided = prev_outcomes["confirmed"] + prev_outcomes["cancelled"]
    cr_now = outcomes["cancelled"] / decided * 100 if decided else 0
    cr_prev = prev_outcomes["cancelled"] / prev_decided * 100 if prev_decided else 0
    if decided >= 10 and cr_now >= 5 and cr_prev and cr_now >= cr_prev * 1.3:
        alert("warn", f"↩️ Cancellations rose to {cr_now:.1f}% of bookings (from {cr_prev:.1f}% in the previous period).")
    started = sum(outcomes.values())
    if started >= 10 and outcomes["expired"] / started >= 0.15:
        alert("warn", f"🛒 {round(outcomes['expired'] / started * 100)}% of bookings were abandoned at payment — "
                      "check the payment step or the seat-lock timer.")
    wd_shows = [0] * 7
    for r in in_period:
        wd_shows[r["start_time"].astimezone(IST).weekday()] += 1
    per_show = [(weekday[i]["tickets"] / wd_shows[i], i) for i in range(7) if wd_shows[i]]
    if len(per_show) >= 3:
        avg_ps = sum(x for x, _ in per_show) / len(per_show)
        worst, wi = min(per_show)
        if avg_ps and worst < avg_ps * 0.5:
            alert("info", f"📅 {WEEKDAYS[wi]} shows sell {round(worst)} tickets each on average, "
                          f"less than half the {round(avg_ps)} average — consider fewer {WEEKDAYS[wi]} shows.")
    if len(by_event) >= 2 and by_event[0]["revenue"] > 0:
        share = by_event[0]["revenue"] / net * 100 if net else 0
        alert("info", f"🏆 {by_event[0]['title']} is your top earner this period ({round(share)}% of revenue).")
    order = {"warn": 0, "good": 1, "info": 2}
    alerts = sorted(alerts, key=lambda a: order[a["level"]])[:8]

    return {
        "scope": "all organizations" if is_admin else "your organization",
        "has_organization": has_org,
        "range": {"start": d_from.isoformat(), "end": d_to.isoformat(), "days": span,
                  "previous_start": p_from.isoformat(), "previous_end": p_to.isoformat()},
        "events": [{"id": str(r["id"]), "title": r["title"], "event_type": r["event_type"]} for r in events],
        "summary": {
            "revenue": round(net, 2),
            "gross_revenue": round(_f(rev["gross"]), 2),
            "refunds": round(_f(rev["refunds"]), 2),
            "revenue_change_pct": _pct_change(net, prev_net),
            "tickets_sold": tickets,
            "tickets_change_pct": _pct_change(tickets, int(prev_tix["tickets"])),
            "confirmed_bookings": tix["bookings"],
            "unique_buyers": tix["buyers"],
            "avg_order_value": round(_f(tix["amount"]) / tix["bookings"], 2) if tix["bookings"] else 0.0,
            "avg_group_size": round(tickets / tix["bookings"], 2) if tix["bookings"] else 0.0,
            "avg_lead_days": avg_lead,
            "avg_ticket_price": round(_f(tix["amount"]) / tickets, 2) if tickets else 0.0,
            "occupancy_pct": round(sold_total / cap_total * 100, 1) if cap_total else None,
            "shows_in_period": len(in_period),
            "cancellations": cancelled_in_period,
            "cancellation_rate_pct": round(outcomes["cancelled"] / decided * 100, 1) if decided else 0.0,
            "avg_rating": _f(rating["avg"]) if rating["avg"] is not None else None,
            "reviews": rating["n"],
            "wishlisted": wishlisted,
        },
        "trend": trend,
        "by_event": by_event,
        "upcoming_shows": [{
            "show_id": str(r["id"]), "title": r["title"], "event_type": r["event_type"],
            "venue": r["venue"], "screen": r["screen"], "start_time": r["start_time"].isoformat(),
            "capacity": r["capacity"], "sold": r["sold"],
            "occupancy": round(r["sold"] / r["capacity"] * 100, 1) if r["capacity"] else 0.0,
            "revenue": round(_f(r["revenue"]), 2), "dynamic_pricing": r["dynamic_pricing"],
            "base_price": _f(r["base_price"]),
        } for r in upcoming],
        "outcomes": outcomes,
        "by_weekday": [{**w, "revenue": round(w["revenue"], 2)} for w in weekday],
        "by_time_slot": [{**slot_map[k], "revenue": round(slot_map[k]["revenue"], 2)} for k, _ in SLOTS],
        "pricing_comparison": pricing,
        "lead_time": {"buckets": lead_buckets, "avg_days": avg_lead, "median_days": median_lead},
        "sales_curve": sales_curve,
        "customers": customers,
        "alerts": alerts,
    }


async def build_event_detail(conn: asyncpg.Connection, owner: Optional[str], event_id: str,
                             d_from: date, d_to: date) -> Optional[dict]:
    """One event: every show with its sales, rating breakdown and latest reviews.

    Returns None when the event does not exist or belongs to another organization.
    """
    event = await conn.fetchrow(
        f"""WITH {MY_EVENTS}
            SELECT e.id, e.title, e.event_type::text AS event_type, e.status::text AS status,
                   e.poster_url, e.language, e.genre, e.duration_minutes
            FROM events e JOIN my_events me ON me.id = e.id""",
        owner, event_id,
    )
    if not event:  # not found, or belongs to another organization
        return None

    shows = await conn.fetch(
        f"""WITH seat_cap AS (
                SELECT ss.show_id, COUNT(*) AS cap, COUNT(*) FILTER (WHERE ss.status = 'booked') AS sold
                FROM show_seats ss JOIN shows s ON s.id = ss.show_id WHERE s.event_id = $1 GROUP BY ss.show_id
            ),
            zone_cap AS (
                SELECT z.show_id, SUM(z.total_capacity) AS cap, SUM(z.booked_count) AS sold
                FROM show_zones z JOIN shows s ON s.id = z.show_id WHERE s.event_id = $1 GROUP BY z.show_id
            ),
            money AS (
                SELECT b.show_id, SUM(p.amount) AS gross, SUM(COALESCE(p.refunded_amount, 0)) AS refunds,
                       SUM(p.amount - COALESCE(p.refunded_amount, 0)) AS revenue
                FROM payments p JOIN bookings b ON b.id = p.booking_id JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = $1 AND p.status IN ('successful', 'refunded') GROUP BY b.show_id
            ),
            paid AS (   -- what confirmed customers actually paid per ticket
                SELECT b.show_id, SUM(b.total_amount) AS amount
                FROM bookings b JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = $1 AND b.status = 'confirmed' GROUP BY b.show_id
            ),
            show_rating AS (   -- rating from reviewers who booked this particular show
                SELECT x.show_id, ROUND(AVG(x.rating)::numeric, 1) AS avg, COUNT(*) AS n
                FROM (SELECT DISTINCT b.show_id, r.user_id, r.rating
                      FROM bookings b
                      JOIN shows s ON s.id = b.show_id
                      JOIN reviews r ON r.user_id = b.user_id AND r.event_id = s.event_id
                      WHERE s.event_id = $1 AND b.status = 'confirmed' AND COALESCE(r.is_draft, false) = false) x
                GROUP BY x.show_id
            ),
            tix AS (
                SELECT b.show_id, COALESCE(SUM({TICKETS}) FILTER (WHERE b.status = 'confirmed'), 0) AS tickets,
                       COUNT(*) FILTER (WHERE b.status = 'cancelled') AS cancelled
                FROM bookings b JOIN shows s ON s.id = b.show_id
                WHERE s.event_id = $1 AND b.status IN ('confirmed', 'cancelled') GROUP BY b.show_id
            )
            SELECT s.id, s.start_time, s.status::text AS status, s.dynamic_pricing, s.base_price,
                   v.name AS venue, sc.name AS screen,
                   COALESCE(c.cap, 0) + COALESCE(z.cap, 0) AS capacity,
                   COALESCE(c.sold, 0) + COALESCE(z.sold, 0) AS sold,
                   COALESCE(m.revenue, 0) AS revenue, COALESCE(m.gross, 0) AS gross, COALESCE(m.refunds, 0) AS refunds,
                   COALESCE(pd.amount, 0) AS paid_amount,
                   COALESCE(t.tickets, 0) AS tickets, COALESCE(t.cancelled, 0) AS cancelled,
                   sr.avg AS rating, COALESCE(sr.n, 0) AS rating_count
            FROM shows s
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            LEFT JOIN seat_cap c ON c.show_id = s.id
            LEFT JOIN zone_cap z ON z.show_id = s.id
            LEFT JOIN money m ON m.show_id = s.id
            LEFT JOIN tix t ON t.show_id = s.id
            LEFT JOIN paid pd ON pd.show_id = s.id
            LEFT JOIN show_rating sr ON sr.show_id = s.id
            WHERE s.event_id = $1
              AND ((s.start_time AT TIME ZONE '{TZ}')::date BETWEEN $2 AND $3 OR s.start_time > now())
            ORDER BY s.start_time""",
        event_id, d_from, d_to,
    )

    dist = await conn.fetch(
        """SELECT LEAST(10, GREATEST(1, ROUND(rating)))::int AS score, COUNT(*) AS n
           FROM reviews WHERE event_id = $1 AND COALESCE(is_draft, false) = false GROUP BY 1""",
        event_id,
    )
    counts = {r["score"]: r["n"] for r in dist}
    total_reviews = sum(counts.values())
    avg = await conn.fetchval(
        "SELECT ROUND(AVG(rating)::numeric, 1) FROM reviews WHERE event_id = $1 AND COALESCE(is_draft, false) = false",
        event_id)
    latest = await conn.fetch(
        """SELECT r.rating, r.headline, LEFT(r.content, 220) AS content,
                  COALESCE(r.published_at, r.updated_at) AS at, u.name AS author
           FROM reviews r JOIN users u ON u.id = r.user_id
           WHERE r.event_id = $1 AND COALESCE(r.is_draft, false) = false
           ORDER BY COALESCE(r.published_at, r.updated_at) DESC NULLS LAST LIMIT 5""",
        event_id,
    )
    wishlisted = await conn.fetchval("SELECT COUNT(*) FROM wishlists WHERE event_id = $1", event_id)

    now = datetime.now(timezone.utc)
    show_list = [{
        "show_id": str(r["id"]),
        "start_time": r["start_time"].isoformat(),
        "status": r["status"],
        "upcoming": r["start_time"] > now,
        "venue": r["venue"], "screen": r["screen"],
        "dynamic_pricing": r["dynamic_pricing"],
        "base_price": _f(r["base_price"]),
        "avg_ticket_price": round(_f(r["paid_amount"]) / int(r["tickets"]), 2) if int(r["tickets"]) else None,
        "capacity": r["capacity"], "sold": r["sold"],
        "occupancy": round(r["sold"] / r["capacity"] * 100, 1) if r["capacity"] else 0.0,
        "gross_revenue": round(_f(r["gross"]), 2), "refunds": round(_f(r["refunds"]), 2),
        "revenue": round(_f(r["revenue"]), 2),
        "tickets": int(r["tickets"]), "cancelled": int(r["cancelled"]),
        "rating": _f(r["rating"]) if r["rating"] is not None else None, "rating_count": int(r["rating_count"]),
    } for r in shows]
    totals = {
        "gross_revenue": round(sum(x["gross_revenue"] for x in show_list), 2),
        "refunds": round(sum(x["refunds"] for x in show_list), 2),
        "revenue": round(sum(x["revenue"] for x in show_list), 2),
        "tickets": sum(x["tickets"] for x in show_list),
        "dynamic_shows": sum(1 for x in show_list if x["dynamic_pricing"]),
        "fixed_shows": sum(1 for x in show_list if not x["dynamic_pricing"]),
    }
    played = [s for s in show_list if not s["upcoming"] and s["capacity"]]
    best = max(played, key=lambda s: s["occupancy"], default=None)

    return {
        "range": {"start": d_from.isoformat(), "end": d_to.isoformat()},
        "event": {
            "id": str(event["id"]), "title": event["title"], "event_type": event["event_type"],
            "status": event["status"], "poster_url": event["poster_url"], "language": event["language"],
            "genre": event["genre"], "duration_minutes": event["duration_minutes"],
        },
        "shows": show_list,
        "totals": totals,
        "best_show_id": best["show_id"] if best else None,
        "ratings": {
            "average": _f(avg) if avg is not None else None,
            "count": total_reviews,
            "distribution": [{"score": i, "count": counts.get(i, 0)} for i in range(10, 0, -1)],
        },
        "latest_reviews": [{
            "rating": _f(r["rating"]), "headline": r["headline"], "content": r["content"],
            "author": r["author"], "at": r["at"].isoformat() if r["at"] else None,
        } for r in latest],
        "wishlisted": wishlisted,
    }


async def transfer_counts(conn: asyncpg.Connection, owner: Optional[str], event_id: Optional[str],
                          d_from: date, d_to: date) -> dict:
    rows = await conn.fetch(
        """SELECT CASE WHEN tt.status = 'pending' AND
                      (tt.created_at + interval '24 hours' <= statement_timestamp()
                       OR s.start_time <= statement_timestamp()) THEN 'expired' ELSE tt.status END AS status,
                  COUNT(*) AS count
           FROM ticket_transfers tt
           JOIN bookings b ON b.id = tt.booking_id
           JOIN shows s ON s.id = b.show_id
           JOIN events e ON e.id = s.event_id
           LEFT JOIN organizer_profiles op ON op.id = e.organizer_id
           WHERE ($1::uuid IS NULL OR op.user_id = $1::uuid)
             AND ($2::uuid IS NULL OR e.id = $2::uuid)
             AND (tt.created_at AT TIME ZONE 'Asia/Kolkata')::date BETWEEN $3 AND $4
           GROUP BY 1""",
        owner, event_id, d_from, d_to,
    )
    counts = {status: 0 for status in ("pending", "accepted", "declined", "cancelled", "expired")}
    for row in rows:
        counts[row["status"]] = row["count"]
    return {"total": sum(counts.values()), "statuses": counts}
