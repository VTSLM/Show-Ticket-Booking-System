from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from app.models import SeatCountInfo

def test_teammate_pricing_handoff_contract(client):
    show_id = "sh111111-1111-1111-1111-111111111111"
    event_id = "e1111111-1111-1111-1111-111111111111"
    screen_id = "s1111111-1111-1111-1111-111111111111"
    now = datetime.now(timezone.utc)

    fake_show = {
        "id": show_id,
        "event_id": event_id,
        "screen_id": screen_id,
        "start_time": now + timedelta(days=1),
        "end_time": now + timedelta(days=1, hours=2),
        "status": "scheduled",
        "created_at": now,
        "updated_at": now,
        "event_title": "Grand Concert",
        "venue_id": "v1111111-1111-1111-1111-111111111111",
        "venue_name": "City Arena",
        "screen_name": "Auditorium A",
        "seat_count": 250,
        "pricing_ready": False,
    }

    seat_info = SeatCountInfo(
        screen_id=screen_id,
        screen_name="Auditorium A",
        venue_id="v1111111-1111-1111-1111-111111111111",
        venue_name="City Arena",
        seat_count=250,
        source="screens_capacity",
        screen_capacity=250,
        seats_table_count=0,
    )

    with patch("app.services.show_service.get_show_by_id", new=AsyncMock(return_value=fake_show)):
        with patch("app.services.show_service.get_screen_seat_info", new=AsyncMock(return_value=seat_info)):
            response = client.get(f"/api/manager/shows/{show_id}/handoff")
            assert response.status_code == 200
            data = response.json()
            assert data["show_id"] == show_id
            assert data["event_id"] == event_id
            assert data["screen_id"] == screen_id
            assert data["seat_count"] == 250
            assert data["pricing_ready"] is False
            expected_route = f"/pricing?show_id={show_id}&event_id={event_id}&screen_id={screen_id}&seat_count=250"
            assert data["pricing_route"] == expected_route
