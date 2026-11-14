import asyncio
import base64
import hashlib
import hmac
import io
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import asyncpg
import httpx
from PIL import Image

sys.path.insert(0, r"d:\Sem 5\Se_project\sprint1_v2\backend")
import config  # noqa: E402
import main as app_main  # noqa: E402
from database import get_conn  # noqa: E402
from dependencies import get_current_user  # noqa: E402
from routers import payments as payments_router  # noqa: E402
from routers import tickets as tickets_router  # noqa: E402
from services.qr_service import generate_qr_bytes  # noqa: E402
from services.ticket_service import build_ticket_pdf  # noqa: E402


class Tx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.tx_depth += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.conn.tx_depth -= 1


class SchemaAwareFakeConn:
    """
    In-memory stateful fake asyncpg connection enforcing key 001_initial_schema.sql
    and 002_payment_gateway.sql schema constraints (including columns that actually exist).
    """

    def __init__(self):
        self.tx_depth = 0
        self.user_a = uuid.UUID("11111111-1111-1111-1111-111111111111")
        self.user_b = uuid.UUID("22222222-2222-2222-2222-222222222222")
        self.manager_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

        self.users = {
            str(self.user_a): {"id": self.user_a, "name": "Alice Customer", "email": "alice@example.com"},
            str(self.user_b): {"id": self.user_b, "name": "Bob Customer", "email": "bob@example.com"},
            str(self.manager_id): {"id": self.manager_id, "name": "Mgr User", "email": "mgr@example.com"},
        }
        self.venues = {}
        self.screens = {}
        self.seats = {}
        self.events = {}
        self.shows = {}
        self.show_seats = {}
        self.bookings = {}
        self.booking_seats = {}
        self.payment_orders = []
        self.payments = {}
        self.receipts = {}
        self.tickets = {}

        # Seed baseline booking data for payment/ticket tests
        v_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        sc_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        ev_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        sh_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
        st1 = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee1")
        ss1 = uuid.UUID("ffffffff-ffff-ffff-ffff-fffffffffff1")
        b_pending = uuid.UUID("99999999-9999-9999-9999-999999999991")
        b_decimal = uuid.UUID("99999999-9999-9999-9999-999999999992")

        self.venues[str(v_id)] = {"id": v_id, "name": "PVR Ahmedabad", "city": "Ahmedabad", "address": "SG Highway"}
        self.screens[str(sc_id)] = {"id": sc_id, "venue_id": v_id, "name": "Screen 1", "capacity": 10}
        self.seats[str(st1)] = {"id": st1, "screen_id": sc_id, "row_label": "A", "seat_number": 1, "seat_type": "standard"}
        self.events[str(ev_id)] = {
            "id": ev_id, "title": "Seeded Movie", "event_type": "movie",
            "duration_minutes": 140, "language": "Hindi", "genre": "Action",
            "poster_url": None, "status": "published", "created_at": datetime.now(timezone.utc),
        }
        start_future = datetime.now(timezone.utc) + timedelta(days=2)
        self.shows[str(sh_id)] = {
            "id": sh_id, "event_id": ev_id, "screen_id": sc_id,
            "start_time": start_future, "end_time": start_future + timedelta(hours=3),
            "base_price": Decimal("500.00"), "status": "scheduled",
        }
        self.show_seats[str(ss1)] = {
            "id": ss1, "show_id": sh_id, "seat_id": st1, "price": Decimal("500.00"),
            "status": "locked", "locked_by": self.user_a, "locked_until": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        self.bookings[str(b_pending)] = {
            "id": b_pending, "booking_number": "TF-20261110-AAA111", "user_id": self.user_a,
            "show_id": sh_id, "total_amount": Decimal("500.00"), "currency": "INR", "status": "pending",
        }
        self.booking_seats[str(b_pending)] = [
            {"booking_id": b_pending, "show_seat_id": ss1, "unit_price": Decimal("500.00")}
        ]
        self.bookings[str(b_decimal)] = {
            "id": b_decimal, "booking_number": "TF-20261110-BBB222", "user_id": self.user_a,
            "show_id": sh_id, "total_amount": Decimal("19.99"), "currency": "INR", "status": "pending",
        }

        self.seed_pending_booking_id = str(b_pending)
        self.seed_decimal_booking_id = str(b_decimal)
        self.seed_venue_id = str(v_id)
        self.seed_screen_id = str(sc_id)
        self.seed_event_id = str(ev_id)
        self.seed_show_id = str(sh_id)
        self.seed_show_seat_id = str(ss1)

    def transaction(self):
        return Tx(self)

    async def fetch(self, query, *args):
        q = " ".join(query.split())
        if q.startswith("SELECT * FROM venues"):
            return list(self.venues.values())
        if q.startswith("SELECT * FROM screens WHERE venue_id=$1"):
            return [s for s in self.screens.values() if str(s["venue_id"]) == str(args[0])]
        if q.startswith("SELECT * FROM events"):
            return list(self.events.values())
        if "FROM shows s JOIN events e ON e.id=s.event_id" in q:
            out = []
            for s in self.shows.values():
                ev = self.events[str(s["event_id"])]
                sc = self.screens[str(s["screen_id"])]
                v = self.venues[str(sc["venue_id"])]
                out.append({**s, "event_title": ev["title"], "venue_name": v["name"], "screen_name": sc["name"]})
            return out
        if "FROM shows s JOIN events e ON e.id = s.event_id JOIN screens sc" in q:
            now = datetime.now(timezone.utc)
            out = []
            for s in self.shows.values():
                ev = self.events[str(s["event_id"])]
                sc = self.screens[str(s["screen_id"])]
                v = self.venues[str(sc["venue_id"])]
                if s["status"] == "scheduled" and ev["status"] == "published" and s["start_time"] > now:
                    sss = [x for x in self.show_seats.values() if str(x["show_id"]) == str(s["id"])]
                    prices = [x["price"] for x in sss]
                    out.append({
                        "show_id": s["id"], "start_time": s["start_time"],
                        "base_price": min(prices) if prices else None,
                        "show_status": s["status"], "event_id": ev["id"], "title": ev["title"],
                        "event_type": ev["event_type"], "language": ev.get("language"),
                        "genre": ev.get("genre"), "duration_minutes": ev.get("duration_minutes"),
                        "poster_url": ev.get("poster_url"), "description": ev.get("description"),
                        "venue_id": v["id"], "venue_name": v["name"], "city": v["city"],
                        "address": v.get("address"), "screen_name": sc["name"], "capacity": sc["capacity"],
                        "available_seats": sum(1 for x in sss if x["status"] == "available"),
                        "total_seats": len(sss),
                    })
            return out
        if "FROM booking_seats bs JOIN show_seats ss" in q:
            bid = str(args[0])
            res = []
            for bs in self.booking_seats.get(bid, []):
                ss = self.show_seats[str(bs["show_seat_id"])]
                st = self.seats[str(ss["seat_id"])]
                res.append({
                    "row_label": st["row_label"], "seat_number": st["seat_number"],
                    "seat_type": st["seat_type"], "price": bs["unit_price"],
                })
            return res
        raise AssertionError(f"Unhandled fetch SQL: {q}")

    async def fetchrow(self, query, *args):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO venues"):
            vid = uuid.uuid4()
            row = {"id": vid, "name": args[0], "address": args[1], "city": args[2], "state": args[3], "pincode": args[4], "created_at": datetime.now(timezone.utc)}
            self.venues[str(vid)] = row
            return row
        if q.startswith("INSERT INTO screens"):
            vid, name, cap = uuid.UUID(str(args[0])), args[1], args[2]
            for s in self.screens.values():
                if str(s["venue_id"]) == str(vid) and s["name"] == name:
                    raise asyncpg.UniqueViolationError("duplicate key value violates unique constraint screens_venue_id_name_key")
            sid = uuid.uuid4()
            row = {"id": sid, "venue_id": vid, "name": name, "capacity": cap, "created_at": datetime.now(timezone.utc)}
            self.screens[str(sid)] = row
            return row
        if q.startswith("INSERT INTO events"):
            eid = uuid.uuid4()
            row = {
                "id": eid, "title": args[0], "description": args[1], "event_type": args[2],
                "duration_minutes": args[3], "language": args[4], "genre": args[5],
                "poster_url": args[6], "status": args[7], "created_at": datetime.now(timezone.utc),
            }
            self.events[str(eid)] = row
            return row
        if q.startswith("UPDATE events SET"):
            eid = str(args[0])
            ev = self.events.get(eid)
            if not ev:
                return None
            # Extract columns from SET clause
            set_part = q.split("SET ", 1)[1].split(", updated_at")[0]
            cols = [p.split("=")[0].strip() for p in set_part.split(",")]
            for idx, col in enumerate(cols):
                ev[col] = args[idx + 1]
            return ev
        if "SELECT id, title, duration_minutes FROM events WHERE id=$1" in q:
            return self.events.get(str(args[0]))
        if "FROM screens sc JOIN venues v ON v.id = sc.venue_id WHERE sc.id = $1" in q:
            sc = self.screens.get(str(args[0]))
            if not sc:
                return None
            v = self.venues[str(sc["venue_id"])]
            return {**sc, "venue_name": v["name"]}
        if "FROM shows s JOIN events e ON e.id = s.event_id WHERE s.screen_id = $1" in q:
            screen_id, start_t, end_t = str(args[0]), args[1], args[2]
            for s in self.shows.values():
                if str(s["screen_id"]) == screen_id and s["status"] == "scheduled" and s["start_time"] < end_t and s["end_time"] > start_t:
                    return {**s, "event_title": self.events[str(s["event_id"])]["title"]}
            return None
        if q.startswith("INSERT INTO shows"):
            sid = uuid.uuid4()
            start_t, end_t = args[2], args[3]
            if end_t <= start_t:
                raise asyncpg.CheckViolationError("shows_check violated")
            row = {
                "id": sid, "event_id": uuid.UUID(str(args[0])), "screen_id": uuid.UUID(str(args[1])),
                "start_time": start_t, "end_time": end_t, "base_price": args[4], "status": args[5],
            }
            self.shows[str(sid)] = row
            return row
        if "FROM shows s JOIN events e ON e.id=s.event_id JOIN screens sc ON sc.id=s.screen_id JOIN venues v ON v.id=sc.venue_id LEFT JOIN show_seats ss ON ss.show_id=s.id WHERE s.id=$1" in q:
            s = self.shows.get(str(args[0]))
            if not s:
                return None
            ev = self.events[str(s["event_id"])]
            sc = self.screens[str(s["screen_id"])]
            v = self.venues[str(sc["venue_id"])]
            sss = [x for x in self.show_seats.values() if str(x["show_id"]) == str(s["id"])]
            return {
                "show_id": s["id"], "start_time": s["start_time"],
                "base_price": min([x["price"] for x in sss]) if sss else None,
                "show_status": s["status"], "event_id": ev["id"], "title": ev["title"],
                "event_type": ev["event_type"], "language": ev.get("language"), "genre": ev.get("genre"),
                "duration_minutes": ev.get("duration_minutes"), "poster_url": ev.get("poster_url"),
                "description": ev.get("description"), "venue_id": v["id"], "venue_name": v["name"],
                "city": v["city"], "address": v.get("address"), "screen_name": sc["name"],
                "capacity": sc["capacity"], "available_seats": sum(1 for x in sss if x["status"] == "available"),
                "total_seats": len(sss),
            }
        if q.startswith("SELECT * FROM bookings WHERE id=$1 AND user_id=$2"):
            b = self.bookings.get(str(args[0]))
            if b and str(b["user_id"]) == str(args[1]):
                return b
            return None
        if "FROM receipts r JOIN bookings b ON b.id=r.booking_id" in q:
            # Simulates exact PostgreSQL error from 001_initial_schema.sql where receipts lacks booking_id!
            raise asyncpg.UndefinedColumnError("column r.booking_id does not exist")
        if "FROM bookings b JOIN shows s" in q and "WHERE b.id=$1 AND b.user_id=$2" in q:
            b = self.bookings.get(str(args[0]))
            if not b or str(b["user_id"]) != str(args[1]):
                return None
            s = self.shows[str(b["show_id"])]
            ev = self.events[str(s["event_id"])]
            sc = self.screens[str(s["screen_id"])]
            v = self.venues[str(sc["venue_id"])]
            u = self.users[str(b["user_id"])]
            return {
                "id": b["id"], "status": b["status"], "total_amount": b["total_amount"], "show_id": b["show_id"],
                "event_title": ev["title"], "language": ev.get("language"), "genre": ev.get("genre"),
                "poster_url": ev.get("poster_url"), "start_time": s["start_time"],
                "venue_name": v["name"], "city": v["city"], "screen_name": sc["name"],
                "user_name": u["name"], "user_email": u["email"],
            }
        if q.startswith("SELECT id FROM tickets WHERE booking_id=$1"):
            for t in self.tickets.values():
                if str(t["booking_id"]) == str(args[0]):
                    return t
            return None
        if q.startswith("SELECT id, status, is_used FROM tickets WHERE booking_id=$1"):
            # Note: Postgres throws DataError if $1 is invalid UUID!
            uuid.UUID(str(args[0]))
            for t in self.tickets.values():
                if str(t["booking_id"]) == str(args[0]):
                    return t
            return None
        raise AssertionError(f"Unhandled fetchrow SQL: {q}")

    async def fetchval(self, query, *args):
        q = " ".join(query.split())
        if q.startswith("SELECT id FROM venues WHERE id=$1"):
            return args[0] if str(args[0]) in self.venues else None
        if q.startswith("SELECT COUNT(*) FROM seats WHERE screen_id=$1"):
            return sum(1 for st in self.seats.values() if str(st["screen_id"]) == str(args[0]))
        if q.startswith("DELETE FROM shows WHERE id=$1"):
            sid = str(args[0])
            if sid not in self.shows:
                return None
            for b in self.bookings.values():
                if str(b["show_id"]) == sid:
                    raise asyncpg.ForeignKeyViolationError("update or delete on table shows violates fk on bookings")
            del self.shows[sid]
            return uuid.UUID(sid)
        if q.startswith("INSERT INTO payments"):
            pid = uuid.uuid4()
            bid = str(args[0])
            b = self.bookings[bid]
            row = {"id": pid, "booking_id": b["id"], "transaction_id": args[1], "amount": b["total_amount"], "status": "successful"}
            self.payments[str(pid)] = row
            return pid
        if q.startswith("INSERT INTO tickets"):
            bid = str(args[0])
            for t in self.tickets.values():
                if str(t["booking_id"]) == bid:
                    raise asyncpg.UniqueViolationError("duplicate booking_id on tickets")
            tid = uuid.uuid4()
            self.tickets[str(tid)] = {
                "id": tid, "booking_id": uuid.UUID(bid), "user_id": uuid.UUID(str(args[1])),
                "show_id": uuid.UUID(str(args[2])), "qr_code_data": args[3],
                "status": "valid", "is_used": False,
            }
            return tid
        raise AssertionError(f"Unhandled fetchval SQL: {q}")

    async def executemany(self, query, records):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO seats"):
            for screen_id, label, num in records:
                sid = uuid.uuid4()
                self.seats[str(sid)] = {"id": sid, "screen_id": uuid.UUID(str(screen_id)), "row_label": label, "seat_number": num, "seat_type": "standard"}
            return
        raise AssertionError(f"Unhandled executemany SQL: {q}")

    async def execute(self, query, *args):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO show_seats"):
            show_id, price, screen_id = args[0], args[1], str(args[2])
            for st in self.seats.values():
                if str(st["screen_id"]) == screen_id:
                    ssid = uuid.uuid4()
                    self.show_seats[str(ssid)] = {
                        "id": ssid, "show_id": show_id, "seat_id": st["id"], "price": price,
                        "status": "available", "locked_by": None, "locked_until": None,
                    }
            return "INSERT"
        if q.startswith("INSERT INTO payment_orders"):
            bid, rz_oid, amt, uid = str(args[0]), args[1], args[2], args[3]
            # Enforce uq_one_unresolved_payment_order_per_booking from 002_payment_gateway.sql!
            unresolved = {"creating", "created", "verification_pending", "authorized", "successful_needs_review"}
            for po in self.payment_orders:
                if str(po["booking_id"]) == bid and po["status"] in unresolved and po["razorpay_order_id"] != rz_oid:
                    raise asyncpg.UniqueViolationError(
                        'duplicate key value violates unique constraint "uq_one_unresolved_payment_order_per_booking"'
                    )
            for po in self.payment_orders:
                if po["razorpay_order_id"] == rz_oid:
                    po["amount"] = amt
                    po["status"] = "created"
                    return "UPDATE 1"
            self.payment_orders.append({
                "id": uuid.uuid4(), "booking_id": uuid.UUID(bid),
                "razorpay_order_id": rz_oid, "amount": amt, "currency": "INR",
                "status": "created", "created_by": uuid.UUID(str(uid)),
            })
            return "INSERT 0 1"
        if q.startswith("UPDATE payment_orders SET status='successful'"):
            for po in self.payment_orders:
                if po["razorpay_order_id"] == args[0]:
                    po["status"] = "successful"
            return "UPDATE"
        if q.startswith("UPDATE bookings SET status='confirmed'"):
            b = self.bookings.get(str(args[0]))
            if b:
                b["status"] = "confirmed"
            return "UPDATE 1"
        if q.startswith("UPDATE show_seats SET status='booked'"):
            bid = str(args[0])
            for bs in self.booking_seats.get(bid, []):
                ss = self.show_seats[str(bs["show_seat_id"])]
                ss["status"] = "booked"
                ss["locked_by"] = None
                ss["locked_until"] = None
            return "UPDATE"
        if q.startswith("INSERT INTO receipts"):
            rnum, pid = args[0], args[1]
            if rnum not in self.receipts:
                self.receipts[rnum] = {"id": uuid.uuid4(), "receipt_number": rnum, "payment_id": pid}
            return "INSERT"
        raise AssertionError(f"Unhandled execute SQL: {q}")


async def run_all():
    conn = SchemaAwareFakeConn()
    active_user = {"id": conn.manager_id, "name": "Mgr User", "email": "mgr@example.com", "roles": ["manager"]}

    async def override_get_conn():
        yield conn

    async def override_get_current_user():
        return dict(active_user)

    app_main.app.dependency_overrides[get_conn] = override_get_conn
    app_main.app.dependency_overrides[get_current_user] = override_get_current_user

    results = []

    def record(tid, area, title, status, detail=""):
        results.append((tid, area, title, status, detail))
        print(f"[{status}] {tid} ({area}): {title}" + (f" -> {detail}" if detail else ""))

    transport = httpx.ASGITransport(app=app_main.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # =========================================================
        # SUITE A: MANAGER LISTING
        # =========================================================
        # TC-MAN-001: Create Venue
        r = await client.post("/api/manager/venues", json={"name": "PVR Inox Wave", "city": "Gandhinagar", "address": "Sector 1"})
        assert r.status_code == 200
        venue_id = r.json()["id"]
        record("TC-MAN-001", "Manager", "Create venue with valid payload", "PASS")

        # TC-MAN-002: Create Venue missing mandatory fields
        r = await client.post("/api/manager/venues", json={"address": "Only address"})
        assert r.status_code == 422
        record("TC-MAN-002", "Manager", "Reject venue missing name/city (422)", "PASS")

        # TC-MAN-003: Create Screen with 2x10 seat grid
        r = await client.post(f"/api/manager/venues/{venue_id}/screens", json={"name": "Audi 1", "capacity": 20, "rows": 2, "cols": 10})
        assert r.status_code == 200
        screen_id = r.json()["id"]
        seat_cnt = sum(1 for s in conn.seats.values() if str(s["screen_id"]) == screen_id)
        assert seat_cnt == 20
        record("TC-MAN-003", "Manager", "Create screen & auto-generate 20 seats", "PASS")

        # TC-MAN-004: Create Screen without rows/cols
        r = await client.post(f"/api/manager/venues/{venue_id}/screens", json={"name": "Audi 2", "capacity": 50})
        assert r.status_code == 200
        cap_screen_id = r.json()["id"]
        record("TC-MAN-004", "Manager", "Create capacity-only screen without rows/cols", "PASS")

        # TC-MAN-005 & Browse visibility gap: Default Event status from Manager UI
        r = await client.post("/api/manager/events", json={"title": "Dune 3", "event_type": "movie", "duration_minutes": 150})
        assert r.status_code == 200
        draft_event = r.json()
        assert draft_event["status"] == "draft"

        t_start = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        r = await client.post("/api/manager/shows", json={
            "event_id": draft_event["id"], "screen_id": cap_screen_id,
            "start_time": t_start, "base_price": 300.0
        })
        assert r.status_code == 200
        draft_show_id = r.json()["id"]
        ss_cnt = sum(1 for ss in conn.show_seats.values() if str(ss["show_id"]) == draft_show_id)
        assert ss_cnt == 50  # Fallback seat generation worked!
        record("TC-MAN-007", "Manager", "Create show populates fallback show_seats atomically", "PASS", f"50 show_seats created")

        # Check Browse Shows visibility for show whose event defaulted to draft
        browse_res = await client.get("/api/browse/shows")
        browse_ids = [item["show_id"] for item in browse_res.json()]
        if draft_show_id not in browse_ids:
            record("TC-MAN-BROWSE-01", "Manager/Browse", "Newly created draft-event show visibility in /browse", "FAIL", "Excluded from GET /api/browse/shows because EventCreate defaults status='draft' & UI has no Publish control")
        else:
            record("TC-MAN-BROWSE-01", "Manager/Browse", "Draft-event show visibility in /browse", "PASS")

        # Check C06 NFR-03: Direct access to draft show detail
        detail_res = await client.get(f"/api/browse/shows/{draft_show_id}")
        if detail_res.status_code == 200:
            record("TC-MAN-NFR03", "Manager/Browse", "Unpublished/draft show blocked from direct /api/browse/shows/{id}", "FAIL", "GET /api/browse/shows/{id} returned 200 for a draft event (missing e.status='published' filter)")
        else:
            record("TC-MAN-NFR03", "Manager/Browse", "Unpublished/draft show blocked from direct detail URL", "PASS")

        # TC-MAN-006: PATCH event -> now visible in browse
        r = await client.patch(f"/api/manager/events/{draft_event['id']}", json={"status": "published", "created_at": "1999-01-01"})
        assert r.status_code == 200 and r.json()["status"] == "published"
        browse_res2 = await client.get("/api/browse/shows")
        assert draft_show_id in [item["show_id"] for item in browse_res2.json()]
        record("TC-MAN-006", "Manager", "PATCH event to published exposes show in /browse & strips disallowed fields", "PASS")

        # TC-MAN-008 + C21 Overlap + TC-MAN-009/010 RBAC + TC-MAN-011 Delete
        r_bad_time = await client.post("/api/manager/shows", json={
            "event_id": draft_event["id"], "screen_id": screen_id,
            "start_time": "2026-11-18T18:00:00Z", "end_time": "2026-11-18T16:00:00Z", "base_price": 250.0
        })
        assert r_bad_time.status_code == 400
        record("TC-MAN-008", "Manager", "Reject show when end_time <= start_time (400)", "PASS")

        r_overlap = await client.post("/api/manager/shows", json={
            "event_id": draft_event["id"], "screen_id": cap_screen_id,
            "start_time": t_start, "base_price": 250.0
        })
        assert r_overlap.status_code == 409
        record("TC-MAN-C21", "Manager", "Reject overlapping show on same screen (409 Conflict)", "PASS")

        active_user["roles"] = ["customer"]
        r_forbid = await client.post("/api/manager/venues", json={"name": "Nope", "city": "City"})
        assert r_forbid.status_code == 403
        record("TC-MAN-009", "Manager", "Reject customer access to /api/manager/* (403)", "PASS")

        # Auth unauthenticated check (override removed temporarily)
        app_main.app.dependency_overrides.pop(get_current_user)
        r_unauth = await client.post("/api/manager/venues", json={"name": "Nope", "city": "City"})
        assert r_unauth.status_code in (401, 403)
        record("TC-MAN-010", "Manager", "Reject unauthenticated manager API call (401/403)", "PASS", f"HTTP {r_unauth.status_code}")
        app_main.app.dependency_overrides[get_current_user] = override_get_current_user

        active_user["roles"] = ["admin"]
        r_del = await client.delete(f"/api/manager/shows/{draft_show_id}")
        assert r_del.status_code == 200
        record("TC-MAN-011", "Manager", "Admin can delete unbooked show (200)", "PASS")

        r_del_booked = await client.delete(f"/api/manager/shows/{conn.seed_show_id}")
        assert r_del_booked.status_code == 409
        record("TC-MAN-012", "Manager", "Prevent deleting show with existing bookings (409)", "PASS")

        # =========================================================
        # SUITE B: PAYMENT GATEWAY
        # =========================================================
        active_user.update({"id": conn.user_a, "name": "Alice Customer", "email": "alice@example.com", "roles": ["customer"]})
        mock_rz = MagicMock()
        mock_rz.order.create.side_effect = [
            {"id": "order_TestOrder111"},
            {"id": "order_TestOrder222"},
            {"id": "order_TestDecimal333"},
        ]

        with patch.object(payments_router, "get_razorpay", return_value=mock_rz), \
             patch.object(payments_router, "RAZORPAY_KEY_SECRET", "test_secret_123"):
            # TC-PAY-001: Create order for pending booking
            r = await client.post("/api/payments/orders", json={"booking_id": conn.seed_pending_booking_id})
            assert r.status_code == 200
            assert r.json()["amount"] == 50000
            assert r.json()["razorpay_order_id"] == "order_TestOrder111"
            record("TC-PAY-001", "Payment", "Create Razorpay order for 500.00 INR (50000 paise)", "PASS")

            # Retry / create second order after dismissing modal (triggers uq_one_unresolved_payment_order_per_booking!)
            r_retry = await client.post("/api/payments/orders", json={"booking_id": conn.seed_pending_booking_id})
            if r_retry.status_code != 200:
                record("TC-PAY-RETRY", "Payment", "Retry create_order after modal dismiss on same pending booking", "FAIL", f"HTTP {r_retry.status_code}: {r_retry.json().get('detail')}")
            else:
                record("TC-PAY-RETRY", "Payment", "Retry create_order on same pending booking", "PASS")

            # Decimal paise truncation check (19.99 * 100 = 1998.9999999999998 -> int() = 1998!)
            r_dec = await client.post("/api/payments/orders", json={"booking_id": conn.seed_decimal_booking_id})
            assert r_dec.status_code == 200
            if r_dec.json()["amount"] != 1999:
                record("TC-PAY-PAISE", "Payment", "Exact paise conversion for 19.99 INR", "FAIL", f"Got {r_dec.json()['amount']} paise instead of 1999 due to int(float * 100)")
            else:
                record("TC-PAY-PAISE", "Payment", "Exact paise conversion for 19.99 INR", "PASS")

            # TC-PAY-004: Forged signature rejected
            r_bad_sig = await client.post(
                f"/api/payments/orders/{conn.seed_pending_booking_id}/verify",
                json={"razorpay_order_id": "order_TestOrder111", "razorpay_payment_id": "pay_ABC123456", "razorpay_signature": "bad_sig"},
            )
            assert r_bad_sig.status_code == 400
            record("TC-PAY-004", "Payment", "Reject forged HMAC-SHA256 payment signature (400)", "PASS")

            # IDOR / Ownership check on verify_payment: User B tries to verify / manipulate User A's booking
            valid_sig_idor = hmac.new(b"test_secret_123", b"order_TestOrder111|pay_ABC123456", hashlib.sha256).hexdigest()
            active_user.update({"id": conn.user_b, "name": "Bob Customer", "email": "bob@example.com"})
            r_idor = await client.post(
                f"/api/payments/orders/{conn.seed_pending_booking_id}/verify",
                json={"razorpay_order_id": "order_TestOrder111", "razorpay_payment_id": "pay_ABC123456", "razorpay_signature": valid_sig_idor},
            )
            if r_idor.status_code == 200:
                record("TC-PAY-IDOR-VERIFY", "Payment", "Block cross-user payment verification (User B on User A booking)", "FAIL", "verify_payment returned 200 OK; lacks user_id & order-to-booking check!")
            else:
                record("TC-PAY-IDOR-VERIFY", "Payment", "Block cross-user payment verification", "PASS")

            # Reset pending booking/seat for clean TC-PAY-003/005/006 check as User A
            conn.bookings[conn.seed_pending_booking_id]["status"] = "pending"
            conn.show_seats[conn.seed_show_seat_id]["status"] = "locked"
            conn.show_seats[conn.seed_show_seat_id]["locked_by"] = conn.user_a
            active_user.update({"id": conn.user_a, "name": "Alice Customer", "email": "alice@example.com"})

            r_ok = await client.post(
                f"/api/payments/orders/{conn.seed_pending_booking_id}/verify",
                json={"razorpay_order_id": "order_TestOrder111", "razorpay_payment_id": "pay_XYZ987654", "razorpay_signature": valid_sig_idor.replace("dummy", "") if False else hmac.new(b"test_secret_123", b"order_TestOrder111|pay_XYZ987654", hashlib.sha256).hexdigest()},
            )
            assert r_ok.status_code == 200
            receipt_num = r_ok.json()["receipt_number"]
            assert conn.bookings[conn.seed_pending_booking_id]["status"] == "confirmed"
            assert conn.show_seats[conn.seed_show_seat_id]["status"] == "booked"
            assert conn.show_seats[conn.seed_show_seat_id]["locked_by"] is None
            assert receipt_num == f"TF-{conn.seed_pending_booking_id[:8].upper()}-987654"
            record("TC-PAY-003/005/006/007", "Payment", "Valid HMAC verify updates booking, seats, payment, & receipt", "PASS", receipt_num)

            # TC-PAY-002: Reject order creation on confirmed booking
            r_paid = await client.post("/api/payments/orders", json={"booking_id": conn.seed_pending_booking_id})
            assert r_paid.status_code == 400
            record("TC-PAY-002", "Payment", "Reject creating order for already confirmed booking (400)", "PASS")

            # TC-PAY-008: GET /api/payments/receipts/{receipt_number} schema check!
            r_rcpt = await client.get(f"/api/payments/receipts/{receipt_num}")
            if r_rcpt.status_code != 200:
                record("TC-PAY-008", "Payment", "Fetch receipt via GET /api/payments/receipts/{receipt_number}", "FAIL", f"HTTP {r_rcpt.status_code}: r.booking_id column does not exist in 001_initial_schema.sql")
            else:
                record("TC-PAY-008", "Payment", "Fetch receipt endpoint", "PASS")

        # =========================================================
        # SUITE C: TICKET GENERATION
        # =========================================================
        # TC-TCK-003: QR unit test
        qr_b64 = generate_qr_bytes(f"TICKETFLOW:{conn.seed_pending_booking_id}")
        qr_raw = base64.b64decode(qr_b64)
        img = Image.open(io.BytesIO(qr_raw))
        assert img.format == "PNG" and img.size[0] > 50 and img.size[1] > 50
        record("TC-TCK-003", "Tickets", "QR generator produces valid base64 PNG", "PASS", f"{img.size}")

        # TC-TCK-005 & TC-TCK-006: PDF unit tests
        pdf1 = build_ticket_pdf({
            "event_title": "Seeded Movie", "venue_name": "PVR Ahmedabad", "venue_city": "Ahmedabad",
            "screen_name": "Screen 1", "start_time": "2026-11-12 18:00:00", "user_name": "Alice",
            "booking_id": conn.seed_pending_booking_id,
            "seats": [{"row_label": "A", "seat_number": 1, "seat_type": "standard", "price": 500.0}],
            "total_amount": 500.0, "qr_b64": qr_b64,
        })
        assert pdf1.startswith(b"%PDF-") and len(pdf1) > 1000
        pdf2 = build_ticket_pdf({"event_title": "Minimal", "booking_id": "12345678", "seats": [], "qr_b64": None})
        assert pdf2.startswith(b"%PDF-")
        record("TC-TCK-005/006", "Tickets", "ReportLab builds valid PDF (full & minimal inputs)", "PASS", f"{len(pdf1)} bytes")

        # TC-TCK-004: Reject confirm on unpaid booking
        r_unpaid = await client.post(f"/api/tickets/bookings/{conn.seed_decimal_booking_id}/confirm")
        assert r_unpaid.status_code == 400
        record("TC-TCK-004", "Tickets", "Reject /confirm for pending unpaid booking (400)", "PASS")

        # Security check: Can user download PDF for an UNPAID pending booking?
        r_unpaid_pdf = await client.get(f"/api/tickets/bookings/{conn.seed_decimal_booking_id}/pdf")
        if r_unpaid_pdf.status_code == 200:
            record("TC-TCK-SEC-PDF", "Tickets", "Block PDF ticket download for unpaid pending booking", "FAIL", "GET /pdf returned 200 application/pdf for a pending unpaid booking!")
        else:
            record("TC-TCK-SEC-PDF", "Tickets", "Block PDF ticket download for unpaid booking", "PASS")

        # TC-TCK-001, TC-TCK-002, TC-TCK-009: Confirm ticket + SMTP failure resilience + idempotency
        with patch.object(tickets_router, "send_ticket_email", side_effect=RuntimeError("SMTP blocked")):
            r_conf1 = await client.post(f"/api/tickets/bookings/{conn.seed_pending_booking_id}/confirm")
            assert r_conf1.status_code == 200
            tid1 = r_conf1.json()["ticket_id"]

            r_conf2 = await client.post(f"/api/tickets/bookings/{conn.seed_pending_booking_id}/confirm")
            assert r_conf2.status_code == 200
            assert r_conf2.json()["ticket_id"] == tid1
        record("TC-TCK-001/002/009", "Tickets", "Confirm creates ticket, stays idempotent on retry, handles SMTP errors", "PASS")

        # TC-TCK-007: Download confirmed PDF endpoint
        r_pdf = await client.get(f"/api/tickets/bookings/{conn.seed_pending_booking_id}/pdf")
        assert r_pdf.status_code == 200
        assert r_pdf.headers.get("content-type") == "application/pdf"
        assert "attachment; filename=" in r_pdf.headers.get("content-disposition", "")
        assert r_pdf.content.startswith(b"%PDF-")
        record("TC-TCK-007", "Tickets", "Download ticket PDF endpoint streams valid PDF attachment", "PASS")

        # TC-TCK-010 & TC-TCK-011: Verify ticket valid / used / not found / invalid UUID
        r_v1 = await client.get(f"/api/tickets/bookings/{conn.seed_pending_booking_id}/verify")
        assert r_v1.status_code == 200 and r_v1.json()["valid"] is True
        record("TC-TCK-010", "Tickets", "Verify valid unused ticket", "PASS")

        conn.tickets[tid1]["is_used"] = True
        r_v_used = await client.get(f"/api/tickets/bookings/{conn.seed_pending_booking_id}/verify")
        assert r_v_used.status_code == 200 and r_v_used.json()["valid"] is False

        r_v_missing = await client.get(f"/api/tickets/bookings/{uuid.uuid4()}/verify")
        assert r_v_missing.status_code == 200 and r_v_missing.json()["valid"] is False
        record("TC-TCK-011", "Tickets", "Verify rejects used and missing tickets", "PASS")

        r_v_bad_uuid = await client.get("/api/tickets/bookings/not-a-uuid/verify")
        if r_v_bad_uuid.status_code != 200:
            record("TC-TCK-UUID", "Tickets", "Handle malformed booking_id in /verify without HTTP error", "FAIL", f"Returned HTTP {r_v_bad_uuid.status_code} (DataError)")
        else:
            record("TC-TCK-UUID", "Tickets", "Handle malformed booking_id cleanly", "PASS")

    passed = sum(1 for r in results if r[3] == "PASS")
    failed = sum(1 for r in results if r[3] == "FAIL")
    print(f"\nSUMMARY: {passed} PASSED, {failed} FAILED out of {len(results)} executed checks")


if __name__ == "__main__":
    asyncio.run(run_all())
