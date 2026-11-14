import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

sys.path.insert(0, r"d:\Sem 5\Se_project\sprint1_v2\backend")
import main as app_main  # noqa: E402
from database import get_conn  # noqa: E402
from dependencies import get_current_user  # noqa: E402


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.in_transaction += 1
        self.conn.transactions_started += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.conn.in_transaction -= 1
        if exc_type is not None:
            self.conn.transactions_rolled_back += 1
        else:
            self.conn.transactions_committed += 1


class FakeConn:
    def __init__(self):
        self.in_transaction = 0
        self.transactions_started = 0
        self.transactions_committed = 0
        self.transactions_rolled_back = 0
        self.event_id = "2a48e32b-9fc3-4339-99f5-9a2bb6b7cdb6"
        self.screen_id = "c3bd24b0-5845-47c1-85b5-f79a4affa57d"
        self.venue_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        self.events = {
            self.event_id: {
                "id": uuid.UUID(self.event_id),
                "title": "Interstellar",
                "duration_minutes": 169,
            }
        }
        self.screens = {
            self.screen_id: {
                "id": uuid.UUID(self.screen_id),
                "name": "Screen 1",
                "capacity": 20,
                "venue_id": uuid.UUID(self.venue_id),
                "venue_name": "PVR Ahmedabad",
            }
        }
        self.shows = []
        self.seats = []
        self.show_seats = []
        self.raise_on_insert = None

    def transaction(self):
        return FakeTransaction(self)

    async def fetchrow(self, query, *args):
        q = " ".join(query.split())
        if "FROM events WHERE id=$1" in q:
            return self.events.get(str(args[0]))
        if "FROM screens sc JOIN venues v" in q and "WHERE sc.id = $1" in q:
            return self.screens.get(str(args[0]))
        if "FROM shows s JOIN events e ON e.id = s.event_id WHERE s.screen_id = $1" in q:
            screen_id, start_utc, end_utc = str(args[0]), args[1], args[2]
            for s in self.shows:
                if (
                    str(s["screen_id"]) == screen_id
                    and s["status"] == "scheduled"
                    and s["start_time"] < end_utc
                    and s["end_time"] > start_utc
                ):
                    return {
                        "id": s["id"],
                        "start_time": s["start_time"],
                        "end_time": s["end_time"],
                        "event_title": self.events[str(s["event_id"])]["title"],
                    }
            return None
        if q.startswith("INSERT INTO shows"):
            if self.raise_on_insert is not None:
                raise self.raise_on_insert
            event_id, screen_id, start_t, end_t, price, status = args
            row = {
                "id": uuid.uuid4(),
                "event_id": uuid.UUID(str(event_id)),
                "screen_id": uuid.UUID(str(screen_id)),
                "start_time": start_t,
                "end_time": end_t,
                "base_price": price,
                "status": status,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            self.shows.append(row)
            return row
        raise AssertionError(f"Unexpected fetchrow SQL: {q}")

    async def fetchval(self, query, *args):
        q = " ".join(query.split())
        if "SELECT COUNT(*) FROM seats WHERE screen_id=$1" in q:
            sid = str(args[0])
            return sum(1 for st in self.seats if st[0] == sid)
        raise AssertionError(f"Unexpected fetchval SQL: {q}")

    async def executemany(self, query, records):
        q = " ".join(query.split())
        if "INSERT INTO seats" in q:
            self.seats.extend(records)
            return
        raise AssertionError(f"Unexpected executemany SQL: {q}")

    async def execute(self, query, *args):
        q = " ".join(query.split())
        if "INSERT INTO show_seats" in q:
            show_id, price, screen_id = args
            matching = [s for s in self.seats if s[0] == str(screen_id)]
            for s in matching:
                self.show_seats.append((show_id, s, price, "available"))
            return f"INSERT 0 {len(matching)}"
        raise AssertionError(f"Unexpected execute SQL: {q}")


async def run_tests():
    fake_conn = FakeConn()
    active_roles = ["manager"]

    async def override_get_conn():
        yield fake_conn

    async def override_get_current_user():
        return {
            "id": uuid.uuid4(),
            "name": "Test User",
            "email": "test@example.com",
            "roles": list(active_roles),
            "status": "active",
        }

    # Add temporary route to verify Starlette/FastAPI global 500 CORS handling
    @app_main.app.get("/__test_unhandled_error")
    async def _boom():
        raise RuntimeError("boom")

    app_main.app.dependency_overrides[get_conn] = override_get_conn
    app_main.app.dependency_overrides[get_current_user] = override_get_current_user

    transport = httpx.ASGITransport(app=app_main.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # 1. User's exact failing payload (end_time < start_time) must return 400 + CORS headers
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-13T04:08:00Z",
                "end_time": "2026-11-12T19:08:00Z",
                "base_price": 500.0,
            },
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000", res.headers
        assert "strictly after start time" in res.json()["detail"].lower()
        print("[PASS] 1. Invalid end_time <= start_time rejected cleanly with 400 + CORS")

        # 2. Manager creates valid show (with omitted end_time -> auto-calculated from duration_minutes)
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://127.0.0.1:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-13T04:08:00Z",
                "base_price": 500.0,
            },
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert res.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
        assert fake_conn.transactions_committed == 1
        assert len(fake_conn.seats) == 20, f"Expected 20 fallback seats, got {len(fake_conn.seats)}"
        assert len(fake_conn.show_seats) == 20, f"Expected 20 show_seats, got {len(fake_conn.show_seats)}"
        print("[PASS] 2. Manager created show atomically with auto end_time, fallback seats, & 127.0.0.1 CORS")

        # 3. Admin creates overlapping show -> must be blocked with 409 Conflict + clear message + CORS
        active_roles[:] = ["admin"]
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-13T05:00:00Z",
                "end_time": "2026-11-13T08:00:00Z",
                "base_price": 500.0,
            },
        )
        assert res.status_code == 409, f"Expected 409, got {res.status_code}: {res.text}"
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "Scheduling conflict" in res.json()["detail"]
        assert fake_conn.transactions_rolled_back >= 1
        print("[PASS] 3. Admin overlapping show rejected cleanly with 409 Conflict + details + CORS")

        # 4. Admin creates non-overlapping show -> succeeds 200 OK
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-13T08:00:00Z",
                "end_time": "2026-11-13T11:00:00Z",
                "base_price": 600.0,
            },
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert len(fake_conn.shows) == 2
        print("[PASS] 4. Admin non-overlapping show created cleanly (200 OK)")

        # 5. Customer role is forbidden (403 + CORS)
        active_roles[:] = ["customer"]
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-13T12:00:00Z",
                "end_time": "2026-11-13T15:00:00Z",
                "base_price": 500.0,
            },
        )
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        print("[PASS] 5. Non-manager/admin rejected with 403 + CORS")

        # 6. Invalid UUID & invalid price (400 / 422 + CORS)
        active_roles[:] = ["manager"]
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": "bad-uuid",
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-14T10:00:00Z",
                "end_time": "2026-11-14T12:00:00Z",
                "base_price": 500.0,
            },
        )
        assert res.status_code == 400 and res.headers.get("access-control-allow-origin") == "http://localhost:3000"

        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-14T10:00:00Z",
                "end_time": "2026-11-14T12:00:00Z",
                "base_price": -10,
            },
        )
        assert res.status_code == 422 and res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        print("[PASS] 6. Invalid UUID (400) and negative base_price (422) both return CORS headers")

        # 7. Simulated Postgres CheckViolationError is mapped to 400 + CORS headers
        class MockCheckViolationError(asyncpg.CheckViolationError):
            constraint_name = "shows_check"

        fake_conn.raise_on_insert = MockCheckViolationError("new row violates constraint")
        res = await client.post(
            "/api/manager/shows",
            headers={"Origin": "http://localhost:3000"},
            json={
                "event_id": fake_conn.event_id,
                "screen_id": fake_conn.screen_id,
                "start_time": "2026-11-15T10:00:00Z",
                "end_time": "2026-11-15T12:00:00Z",
                "base_price": 500.0,
            },
        )
        fake_conn.raise_on_insert = None
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "end time" in res.json()["detail"].lower()
        print("[PASS] 7. Simulated CheckViolationError returns 400 JSON + CORS headers")

        # 8. Unhandled RuntimeError (500) ALSO preserves CORS headers instead of causing browser 'Failed to fetch'
        res = await client.get(
            "/__test_unhandled_error",
            headers={"Origin": "http://localhost:3000"},
        )
        assert res.status_code == 500
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        print("[PASS] 8. Unhandled 500 exception still includes Access-Control-Allow-Origin")

    print("\nALL BACKEND VERIFICATION TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(run_tests())
