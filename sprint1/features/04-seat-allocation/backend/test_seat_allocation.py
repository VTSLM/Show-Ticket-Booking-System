"""
test_seat_allocation.py
=======================
Automated test suite covering all 7 phases of Feature 04: Seat Selection & Allocation.
Runs against FastAPI TestClient (httpx).

Run:
    python test_seat_allocation.py
"""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from main import app, MAX_SEATS_PER_BOOKING, LOCK_DURATION_MINUTES
from fixture_seats import (
    _seat_store,
    _SEAT_FIXTURE,
    sweep_expired_locks,
    get_all_seats,
    get_seat,
    atomic_lock_seats,
    confirm_seats,
    cancel_booking,
    release_seats,
)
from copy import deepcopy


class TestSeatAllocationAllPhases(unittest.TestCase):
    def setUp(self):
        """Reset the in-memory seat store before each test for test isolation."""
        _seat_store.clear()
        for seat in _SEAT_FIXTURE:
            _seat_store[seat["id"]] = deepcopy(seat)
        self.client = TestClient(app)
        self.demo_user = "user-test-khushi"
        self.show_id = "show-demo-001"

    # =========================================================================
    # PHASE 1: Fixture Data Structure & Contract Tests
    # =========================================================================
    def test_phase1_fixture_seat_shape(self):
        """Verify fixture seats conform to the shared contract schema."""
        seats = get_all_seats(self.show_id)
        self.assertGreaterEqual(len(seats), 20, "Should have at least 20 fixture seats")

        required_fields = ["id", "row", "number", "section", "status", "price"]
        valid_statuses = {"available", "locked", "booked", "blocked"}
        valid_sections = {"VIP", "PREMIUM", "GENERAL"}

        statuses_found = set()
        sections_found = set()

        for s in seats:
            for field in required_fields:
                self.assertIn(field, s, f"Seat {s.get('id')} missing field {field}")
            self.assertIn(s["status"], valid_statuses)
            self.assertIn(s["section"], valid_sections)
            self.assertIsInstance(s["price"], int)
            self.assertGreater(s["price"], 0)
            statuses_found.add(s["status"])
            sections_found.add(s["section"])

        # Check all statuses and sections are represented in fixture
        self.assertEqual(statuses_found, valid_statuses, "Fixture must include available, locked, booked, and blocked seats")
        self.assertEqual(sections_found, valid_sections, "Fixture must include VIP, PREMIUM, and GENERAL sections")

    # =========================================================================
    # PHASE 2: Seat Map Retrieval API
    # =========================================================================
    def test_phase2_get_seats_endpoint(self):
        """GET /api/shows/{show_id}/seats returns the layout with max seat cap."""
        res = self.client.get(f"/api/shows/{self.show_id}/seats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["show_id"], self.show_id)
        self.assertEqual(data["max_seats_per_booking"], MAX_SEATS_PER_BOOKING)
        self.assertIsInstance(data["seats"], list)
        self.assertGreaterEqual(len(data["seats"]), 20)

    # =========================================================================
    # PHASE 3: Atomic Lock (Compare-and-Swap)
    # =========================================================================
    def test_phase3_atomic_lock_success(self):
        """POST /api/seats/lock successfully locks available seats and sets expiry."""
        # V1-S1 and V1-S2 are available
        req_data = {
            "seat_ids": ["V1-S1", "V1-S2"],
            "user_id": self.demo_user,
            "show_id": self.show_id,
        }
        res = self.client.post("/api/seats/lock", json=req_data)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["locked_seat_ids"], ["V1-S1", "V1-S2"])
        self.assertIn("expires_at", body)

        # Verify status in store
        seat1 = get_seat("V1-S1")
        seat2 = get_seat("V1-S2")
        self.assertEqual(seat1["status"], "locked")
        self.assertEqual(seat1["locked_by"], self.demo_user)
        self.assertEqual(seat2["status"], "locked")
        self.assertEqual(seat2["locked_by"], self.demo_user)

    def test_phase3_atomic_lock_conflict_all_or_nothing(self):
        """
        POST /api/seats/lock with 1 available and 1 already-booked seat.
        Must fail atomically with 409 Conflict; the available seat must NOT be locked.
        """
        # V1-S1 is available, V1-S3 is booked
        req_data = {
            "seat_ids": ["V1-S1", "V1-S3"],
            "user_id": self.demo_user,
            "show_id": self.show_id,
        }
        res = self.client.post("/api/seats/lock", json=req_data)
        self.assertEqual(res.status_code, 409)
        detail = res.json()["detail"]
        self.assertIn("failed_seat_ids", detail)
        self.assertIn("V1-S3", detail["failed_seat_ids"])

        # Crucial CAS invariant: V1-S1 MUST STILL BE AVAILABLE (no partial lock)
        seat1 = get_seat("V1-S1")
        self.assertEqual(seat1["status"], "available", "All-or-nothing violated! V1-S1 should remain available")

    def test_phase3_lock_enforces_max_seats_limit(self):
        """POST /api/seats/lock exceeding MAX_SEATS_PER_BOOKING (6) returns 400 Bad Request."""
        too_many_seats = [f"G1-S{i}" for i in range(1, MAX_SEATS_PER_BOOKING + 2)]
        req_data = {
            "seat_ids": too_many_seats,
            "user_id": self.demo_user,
            "show_id": self.show_id,
        }
        res = self.client.post("/api/seats/lock", json=req_data)
        self.assertEqual(res.status_code, 400)
        self.assertIn(f"Cannot book more than {MAX_SEATS_PER_BOOKING}", res.json()["detail"])

    # =========================================================================
    # PHASE 4: Hold Countdown & Auto-Expiry / Manual Release
    # =========================================================================
    def test_phase4_manual_release(self):
        """POST /api/seats/release releases user's locked seats immediately."""
        # First lock
        self.client.post(
            "/api/seats/lock",
            json={"seat_ids": ["P1-S1"], "user_id": self.demo_user, "show_id": self.show_id},
        )
        self.assertEqual(get_seat("P1-S1")["status"], "locked")

        # Now release
        res = self.client.post(
            "/api/seats/release",
            json={"seat_ids": ["P1-S1"], "user_id": self.demo_user, "show_id": self.show_id},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(get_seat("P1-S1")["status"], "available")
        self.assertIsNone(get_seat("P1-S1")["locked_by"])

    def test_phase4_auto_expiry_sweeper(self):
        """Background sweeper automatically frees locks past expires_at timestamp."""
        # Manually create an expired lock
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        _seat_store["P1-S1"]["status"] = "locked"
        _seat_store["P1-S1"]["locked_by"] = "other-user"
        _seat_store["P1-S1"]["expires_at"] = past_time

        released = sweep_expired_locks()
        self.assertIn("P1-S1", released)
        self.assertEqual(get_seat("P1-S1")["status"], "available")
        self.assertIsNone(get_seat("P1-S1")["locked_by"])

    # =========================================================================
    # PHASE 5: Confirm Booking & Cancellation (FR13)
    # =========================================================================
    def test_phase5_confirm_booking_success(self):
        """POST /api/seats/confirm transitions locked -> booked and returns booking ID."""
        # Lock first
        self.client.post(
            "/api/seats/lock",
            json={"seat_ids": ["V1-S4"], "user_id": self.demo_user, "show_id": self.show_id},
        )

        # Confirm
        res = self.client.post(
            "/api/seats/confirm",
            json={"seat_ids": ["V1-S4"], "user_id": self.demo_user, "show_id": self.show_id},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        booking_id = data["booking_id"]
        self.assertTrue(booking_id.startswith("BKG-"))

        # Verify seat is booked
        self.assertEqual(get_seat("V1-S4")["status"], "booked")

    def test_phase5_cancellation_releases_seats(self):
        """POST /api/bookings/cancel transitions booked -> available (FR13)."""
        # Lock & confirm
        self.client.post(
            "/api/seats/lock",
            json={"seat_ids": ["V1-S6"], "user_id": self.demo_user, "show_id": self.show_id},
        )
        conf_res = self.client.post(
            "/api/seats/confirm",
            json={"seat_ids": ["V1-S6"], "user_id": self.demo_user, "show_id": self.show_id},
        )
        booking_id = conf_res.json()["booking_id"]

        # Cancel booking
        res = self.client.post(
            "/api/bookings/cancel",
            json={"booking_id": booking_id, "user_id": self.demo_user},
        )
        self.assertEqual(res.status_code, 200)

        # Verify seat re-enters available pool
        self.assertEqual(get_seat("V1-S6")["status"], "available")

    # =========================================================================
    # PHASE 7: Failure UX / Expired Lock Rejection
    # =========================================================================
    def test_phase7_confirm_fails_when_lock_expired(self):
        """
        POST /api/seats/confirm with an expired lock must be rejected with 409
        and error_code: LOCK_EXPIRED, so the UI can redirect the user with clear messaging.
        """
        # Set expired lock on P2-S1
        past_time = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        _seat_store["P2-S1"]["status"] = "locked"
        _seat_store["P2-S1"]["locked_by"] = self.demo_user
        _seat_store["P2-S1"]["expires_at"] = past_time

        res = self.client.post(
            "/api/seats/confirm",
            json={"seat_ids": ["P2-S1"], "user_id": self.demo_user, "show_id": self.show_id},
        )
        self.assertEqual(res.status_code, 409)
        detail = res.json()["detail"]
        self.assertEqual(detail["error_code"], "LOCK_EXPIRED")


if __name__ == "__main__":
    unittest.main()
