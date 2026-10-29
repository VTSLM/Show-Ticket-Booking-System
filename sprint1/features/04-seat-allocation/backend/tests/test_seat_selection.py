import uuid
import asyncio
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from app.config import settings
from app.main import app
from tests.conftest import check_is_db_live


# ==============================================================================
# SECTION A: Offline / Validation Tests (Run in all environments)
# ==============================================================================

def test_health_endpoint_response_shape(client: TestClient):
    """GET /api/health should always return app status."""
    res = client.get("/api/health")
    assert res.status_code in (200, 503)
    data = res.json()
    assert "app" in data
    assert "db" in data
    assert "timestamp" in data


def test_unauthenticated_request_rejected(client: TestClient):
    """POST /api/shows/{id}/holds without auth header must return 401 UNAUTHENTICATED."""
    fake_show_id = str(uuid.uuid4())
    res = client.post(
        f"/api/shows/{fake_show_id}/holds",
        json={"show_seat_ids": [str(uuid.uuid4())]},
        headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    assert res.status_code == 401
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_missing_idempotency_key_rejected(client: TestClient):
    """POST /api/shows/{id}/holds without Idempotency-Key header must return 400 VALIDATION_ERROR."""
    fake_show_id = str(uuid.uuid4())
    res = client.post(
        f"/api/shows/{fake_show_id}/holds",
        json={"show_seat_ids": [str(uuid.uuid4())]},
        headers={"Authorization": "Bearer dev-token"}
    )
    assert res.status_code == 400
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_empty_seat_selection_rejected(client: TestClient):
    """POST /api/shows/{id}/holds with empty show_seat_ids list must return 400."""
    fake_show_id = str(uuid.uuid4())
    res = client.post(
        f"/api/shows/{fake_show_id}/holds",
        json={"show_seat_ids": []},
        headers={
            "Authorization": "Bearer dev-token",
            "Idempotency-Key": str(uuid.uuid4())
        }
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_seat_ids_rejected(client: TestClient):
    """POST /api/shows/{id}/holds with duplicated seat IDs must return 400."""
    fake_show_id = str(uuid.uuid4())
    seat_id = str(uuid.uuid4())
    res = client.post(
        f"/api/shows/{fake_show_id}/holds",
        json={"show_seat_ids": [seat_id, seat_id]},
        headers={
            "Authorization": "Bearer dev-token",
            "Idempotency-Key": str(uuid.uuid4())
        }
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_max_seats_exceeded_enforcement(client: TestClient):
    """Requesting more than MAX_SEATS_PER_BOOKING (8) must return 400 MAX_SEATS_EXCEEDED."""
    fake_show_id = str(uuid.uuid4())
    nine_seats = [str(uuid.uuid4()) for _ in range(settings.MAX_SEATS_PER_BOOKING + 1)]
    res = client.post(
        f"/api/shows/{fake_show_id}/holds",
        json={"show_seat_ids": nine_seats},
        headers={
            "Authorization": "Bearer dev-token",
            "Idempotency-Key": str(uuid.uuid4())
        }
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "MAX_SEATS_EXCEEDED"
    assert f"Cannot select more than {settings.MAX_SEATS_PER_BOOKING} seats" in body["error"]["message"]


# ==============================================================================
# SECTION B: Live Database Concurrency & Atomicity Tests
# ==============================================================================

def test_simultaneous_20_holds_on_single_seat():
    """
    CONCURRENCY TEST: 20 simultaneous hold requests for the exact same seat.
    Requirement: Exactly one succeeds (201 Created), 19 fail (409 Conflict SEATS_UNAVAILABLE).
    No race conditions, no double booking.
    """
    if not check_is_db_live():
        pytest.skip("DATABASE_URL is not configured or PostgreSQL is unreachable. Skipping live concurrency test.")

    async def _run():
        from app.services.db import get_pool
        pool = get_pool()
        assert pool is not None

        async with pool.acquire() as conn:
            seat_record = await conn.fetchrow(
                """
                SELECT ss.id AS show_seat_id, ss.show_id
                FROM show_seats ss
                JOIN shows s ON s.id = ss.show_id
                WHERE s.status = 'scheduled' AND s.start_time > NOW() AND ss.status = 'available'
                LIMIT 1;
                """
            )
            if not seat_record:
                pytest.skip("No available scheduled show seats found in DB.")

            show_id = str(seat_record["show_id"])
            seat_id = str(seat_record["show_seat_id"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            async def attempt_hold(i: int):
                idem_key = str(uuid.uuid4())
                user_header = f"Bearer dev-user-{i}"
                return await client.post(
                    f"/api/shows/{show_id}/holds",
                    json={"show_seat_ids": [seat_id]},
                    headers={"Authorization": user_header, "Idempotency-Key": idem_key}
                )

            tasks = [attempt_hold(i) for i in range(20)]
            responses = await asyncio.gather(*tasks)

        success_count = sum(1 for r in responses if r.status_code == 201)
        conflict_count = sum(1 for r in responses if r.status_code == 409)

        assert success_count == 1, f"Expected exactly 1 successful hold, got {success_count}"
        assert conflict_count == 19, f"Expected 19 conflicts, got {conflict_count}"

        conflicts = [r.json() for r in responses if r.status_code == 409]
        for c in conflicts:
            assert c["error"]["code"] == "SEATS_UNAVAILABLE"
            assert seat_id in c["error"]["details"]["failed_seat_ids"]

    asyncio.run(_run())


def test_all_or_nothing_atomicity():
    """
    ATOMICITY TEST: Request holding 2 seats where 1 is available and 1 is already taken.
    The request must fail completely (409 Conflict) and the available seat must NOT be locked.
    """
    if not check_is_db_live():
        pytest.skip("DATABASE_URL is not configured or PostgreSQL is unreachable. Skipping atomicity test.")

    async def _run():
        from app.services.db import get_pool
        pool = get_pool()
        assert pool is not None

        async with pool.acquire() as conn:
            seats = await conn.fetch(
                """
                SELECT ss.id, ss.show_id, ss.status
                FROM show_seats ss
                JOIN shows s ON s.id = ss.show_id
                WHERE s.status = 'scheduled' AND s.start_time > NOW()
                LIMIT 2;
                """
            )
            if len(seats) < 2:
                pytest.skip("Insufficient seats in DB for atomicity test.")

            show_id = str(seats[0]["show_id"])
            seat_a = str(seats[0]["id"])
            seat_b = str(seats[1]["id"])

            await conn.execute("UPDATE show_seats SET status = 'available', locked_by = NULL WHERE id = $1", seats[0]["id"])
            await conn.execute("UPDATE show_seats SET status = 'booked', locked_by = NULL WHERE id = $1", seats[1]["id"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            res = await client.post(
                f"/api/shows/{show_id}/holds",
                json={"show_seat_ids": [seat_a, seat_b]},
                headers={"Authorization": "Bearer dev-token", "Idempotency-Key": str(uuid.uuid4())}
            )
            assert res.status_code == 409
            body = res.json()
            assert body["error"]["code"] == "SEATS_UNAVAILABLE"
            assert seat_b in body["error"]["details"]["failed_seat_ids"]

        async with pool.acquire() as conn:
            status_a = await conn.fetchval("SELECT status FROM show_seats WHERE id = $1", seats[0]["id"])
            assert status_a == "available", "All-or-nothing atomicity violated! Seat was locked."

    asyncio.run(_run())


def test_idempotency_replay():
    """IDEMPOTENCY TEST: Replaying the same Idempotency-Key must return the same booking."""
    if not check_is_db_live():
        pytest.skip("DATABASE_URL is not configured or PostgreSQL is unreachable. Skipping idempotency test.")

    async def _run():
        from app.services.db import get_pool
        pool = get_pool()
        assert pool is not None

        async with pool.acquire() as conn:
            seat = await conn.fetchrow(
                """
                SELECT ss.id, ss.show_id
                FROM show_seats ss
                JOIN shows s ON s.id = ss.show_id
                WHERE s.status = 'scheduled' AND s.start_time > NOW() AND ss.status = 'available'
                LIMIT 1;
                """
            )
            if not seat:
                pytest.skip("No available seat in DB for idempotency test.")

            show_id = str(seat["show_id"])
            seat_id = str(seat["id"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            idem_key = f"idem-test-{uuid.uuid4()}"
            res1 = await client.post(
                f"/api/shows/{show_id}/holds",
                json={"show_seat_ids": [seat_id]},
                headers={"Authorization": "Bearer dev-token", "Idempotency-Key": idem_key}
            )
            assert res1.status_code == 201
            booking1 = res1.json()

            res2 = await client.post(
                f"/api/shows/{show_id}/holds",
                json={"show_seat_ids": [seat_id]},
                headers={"Authorization": "Bearer dev-token", "Idempotency-Key": idem_key}
            )
            assert res2.status_code in (200, 201)
            booking2 = res2.json()

            assert booking1["booking_id"] == booking2["booking_id"]
            assert booking1["booking_number"] == booking2["booking_number"]

    asyncio.run(_run())


def test_owner_only_access_isolation():
    """SECURITY TEST: User B cannot access User A's hold booking. Returns 404."""
    if not check_is_db_live():
        pytest.skip("DATABASE_URL is not configured or PostgreSQL is unreachable. Skipping owner isolation test.")

    async def _run():
        from app.services.db import get_pool
        pool = get_pool()
        assert pool is not None

        async with pool.acquire() as conn:
            seat = await conn.fetchrow(
                """
                SELECT ss.id, ss.show_id
                FROM show_seats ss
                JOIN shows s ON s.id = ss.show_id
                WHERE s.status = 'scheduled' AND s.start_time > NOW() AND ss.status = 'available'
                LIMIT 1;
                """
            )
            if not seat:
                pytest.skip("No available seat for owner test.")
            show_id = str(seat["show_id"])
            seat_id = str(seat["id"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            hold_res = await client.post(
                f"/api/shows/{show_id}/holds",
                json={"show_seat_ids": [seat_id]},
                headers={"Authorization": "Bearer dev-user-a", "Idempotency-Key": str(uuid.uuid4())}
            )
            assert hold_res.status_code == 201
            booking_id = hold_res.json()["booking_id"]

            get_res = await client.get(
                f"/api/holds/{booking_id}",
                headers={"Authorization": "Bearer dev-user-b"}
            )
            assert get_res.status_code == 404
            assert get_res.json()["error"]["code"] == "NOT_FOUND"

            del_res = await client.delete(
                f"/api/holds/{booking_id}",
                headers={"Authorization": "Bearer dev-user-b"}
            )
            assert del_res.status_code == 404
            assert del_res.json()["error"]["code"] == "NOT_FOUND"

    asyncio.run(_run())
