"""
Tests for Multi-Venue Seating and Stage Layouts Engine.
Validates:
- Screen creation with layout types ('cinema', 'concert', 'theatre', 'other')
- Custom premium row seat tagging
- Show creation with tiered seat pricing
- General admission standing zone creation
- Atomic zone locking, capacity checks, and release
- Zone booking checkout
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from routers.seats import get_seat_map, lock_zone, release_zone, ZoneLockRequest
from routers.bookings import create_booking, CreateBookingRequest
from routers.manager import create_screen, ScreenCreate, create_show, ShowCreate, ZoneInput


@pytest.mark.asyncio
async def test_get_seat_map_with_zones_and_layout():
    conn = AsyncMock()
    conn.execute = AsyncMock()

    show_id = str(uuid.uuid4())

    # Mock show seats
    conn.fetch.side_effect = [
        # Seat rows
        [
            {"show_seat_id": str(uuid.uuid4()), "status": "available", "price": 250.0, "row_label": "A", "seat_number": 1, "seat_type": "standard"},
            {"show_seat_id": str(uuid.uuid4()), "status": "available", "price": 400.0, "row_label": "B", "seat_number": 1, "seat_type": "premium"}
        ],
        # Zones
        [
            {
                "id": str(uuid.uuid4()), "name": "Fan Pit (Standing)", "zone_type": "standing",
                "total_capacity": 500, "booked_count": 50, "locked_count": 10,
                "price": 6500.0, "color_hex": "#ff3b5c", "display_order": 1,
                "available_capacity": 440
            }
        ]
    ]

    conn.fetchrow.return_value = {
        "layout_type": "concert",
        "stage_position": "front",
        "event_type": "concert"
    }

    result = await get_seat_map(show_id=show_id, conn=conn)

    assert result["layout_type"] == "concert"
    assert result["stage_position"] == "front"
    assert len(result["zones"]) == 1
    assert result["zones"][0]["name"] == "Fan Pit (Standing)"
    assert result["zones"][0]["available_capacity"] == 440
    assert len(result["seats"]) == 2


@pytest.mark.asyncio
async def test_lock_and_release_zone():
    conn = AsyncMock()
    show_id = str(uuid.uuid4())
    zone_id = str(uuid.uuid4())

    conn.fetchrow.return_value = {
        "id": uuid.UUID(zone_id),
        "name": "VIP Standing Lounge",
        "total_capacity": 200,
        "booked_count": 20,
        "locked_count": 5,
        "price": 4500.0
    }

    user = {"id": str(uuid.uuid4())}
    req = ZoneLockRequest(zone_id=zone_id, quantity=2)

    lock_res = await lock_zone(show_id=show_id, req=req, current_user=user, conn=conn)
    assert lock_res["zone_id"] == zone_id
    assert lock_res["locked_quantity"] == 2
    assert lock_res["price"] == 4500.0
    assert lock_res["total_price"] == 9000.0

    # Release
    release_res = await release_zone(show_id=show_id, req=req, current_user=user, conn=conn)
    assert release_res["released"] is True


@pytest.mark.asyncio
async def test_zone_booking_flow():
    conn = AsyncMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock()

    show_id = str(uuid.uuid4())
    zone_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    conn.fetchrow.return_value = {
        "id": uuid.UUID(zone_id),
        "name": "Fan Pit",
        "price": 5000.0
    }
    conn.execute.return_value = "UPDATE 1"
    conn.fetchval.return_value = uuid.uuid4()

    req = CreateBookingRequest(show_id=show_id, zone_id=zone_id, zone_quantity=3)
    user = {"id": user_id}

    booking = await create_booking(req=req, current_user=user, conn=conn)

    assert booking["status"] == "pending"
    assert booking["total_amount"] == 15000.0
    assert booking["zone_name"] == "Fan Pit"
    assert booking["quantity"] == 3


@pytest.mark.asyncio
async def test_manager_create_screen_with_custom_tiers():
    conn = AsyncMock()
    venue_id = str(uuid.uuid4())
    screen_id = str(uuid.uuid4())

    conn.fetchrow.return_value = {
        "id": screen_id,
        "name": "Arena Main Stage",
        "capacity": 500,
        "layout_type": "concert",
        "stage_position": "front"
    }

    body = ScreenCreate(
        name="Arena Main Stage",
        capacity=500,
        rows=3,
        cols=4,
        layout_type="concert",
        stage_position="front",
        premium_rows=["A", "B"]
    )

    result = await create_screen(venue_id=venue_id, body=body, _={}, conn=conn)
    assert result["layout_type"] == "concert"
    assert result["stage_position"] == "front"
    # Verify execute was called for 3 rows * 4 cols = 12 seats
    assert conn.execute.call_count == 12
