import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import asyncpg
import pytest
from fastapi.testclient import TestClient

import main as app_main
from database import get_conn
from dependencies import get_current_user


class FakeTx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.tx_depth += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.conn.tx_depth -= 1


class SchemaAwareFakeConn:
    """In-memory fake asyncpg connection matching 001_initial_schema.sql and 002_payment_gateway.sql."""

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
        return FakeTx(self)

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
            try:
                uuid.UUID(str(args[0]))
            except ValueError as exc:
                raise asyncpg.DataError(f'invalid input syntax for type uuid: "{args[0]}"') from exc
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
            unresolved = {"creating", "created", "verification_pending", "authorized", "successful_needs_review"}
            for po in self.payment_orders:
                if str(po["booking_id"]) == bid and po["status"] in unresolved and po["razorpay_order_id"] != rz_oid:
                    raise asyncpg.UniqueViolationError(
                        'duplicate key value violates unique constraint "uq_one_unresolved_payment_order_per_booking"'
                    )
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


@pytest.fixture
def fake_db():
    return SchemaAwareFakeConn()


@pytest.fixture
def active_user(fake_db):
    return {"id": fake_db.manager_id, "name": "Mgr User", "email": "mgr@example.com", "roles": ["manager"]}


@pytest.fixture
def client(fake_db, active_user):
    async def override_get_conn():
        yield fake_db

    async def override_get_current_user():
        return dict(active_user)

    app_main.app.dependency_overrides[get_conn] = override_get_conn
    app_main.app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app_main.app, raise_server_exceptions=False) as tc:
        yield tc
    app_main.app.dependency_overrides.clear()

