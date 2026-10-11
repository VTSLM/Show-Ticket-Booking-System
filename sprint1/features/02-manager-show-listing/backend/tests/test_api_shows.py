from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from app.models import SeatCountInfo

def test_create_valid_show(client):
    now = datetime.now(timezone.utc)
    start = now + timedelta(days=2)
    end = start + timedelta(hours=2)

    event_row = {"id": "e1111111-1111-1111-1111-111111111111", "title": "Demo Movie", "duration_minutes": 120}
    screen_row = {"id": "s1111111-1111-1111-1111-111111111111", "venue_id": "v1111111-1111-1111-1111-111111111111", "name": "Screen 1", "capacity": 100}
    created_row = {
        "id": "sh111111-1111-1111-1111-111111111111",
        "event_id": event_row["id"],
        "screen_id": screen_row["id"],
        "start_time": start,
        "end_time": end,
        "status": "scheduled",
        "created_at": now,
        "updated_at": now,
    }

    seat_info = SeatCountInfo(
        screen_id=screen_row["id"],
        screen_name="Screen 1",
        venue_id=screen_row["venue_id"],
        venue_name="Demo Cinema",
        seat_count=100,
        source="screens_capacity",
        screen_capacity=100,
        seats_table_count=0
    )

    with patch("app.services.show_service.fetch_one", new=AsyncMock()) as mock_fetch:
        mock_fetch.side_effect = [event_row, screen_row, None, created_row]

        with patch("app.services.show_service.get_screen_seat_info", new=AsyncMock(return_value=seat_info)):
            response = client.post(
                "/api/manager/shows",
                json={
                    "event_id": event_row["id"],
                    "screen_id": screen_row["id"],
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "sh111111-1111-1111-1111-111111111111"
            assert data["status"] == "scheduled"
            assert data["pricing_ready"] is False

def test_create_show_missing_event(client):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    with patch("app.services.show_service.fetch_one", new=AsyncMock(return_value=None)):
        response = client.post(
            "/api/manager/shows",
            json={
                "event_id": "00000000-0000-0000-0000-000000000099",
                "screen_id": "00000000-0000-0000-0000-000000000088",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 404
        assert "Event with ID" in response.json()["detail"]

def test_create_show_invalid_end_time(client):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start - timedelta(hours=1)

    response = client.post(
        "/api/manager/shows",
        json={
            "event_id": "e1111111-1111-1111-1111-111111111111",
            "screen_id": "s1111111-1111-1111-1111-111111111111",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )
    assert response.status_code == 422

def test_delete_show_success(client):
    fake_show_id = "sh111111-2222-3333-4444-555555555555"
    fake_show = {"id": fake_show_id, "event_title": "Show To Delete"}
    booking_check = {"count": 0}

    with patch("app.services.show_service.get_show_by_id", new=AsyncMock(return_value=fake_show)), \
         patch("app.services.show_service.fetch_one", new=AsyncMock(return_value=booking_check)), \
         patch("app.services.show_service.execute", new_callable=AsyncMock) as mock_exec:
        res = client.delete(f"/api/manager/shows/{fake_show_id}")
        assert res.status_code == 200
        assert res.json()["message"] == "Show successfully deleted"
        assert mock_exec.call_count == 2

def test_delete_show_with_bookings_fails(client):
    fake_show_id = "sh111111-2222-3333-4444-555555555555"
    fake_show = {"id": fake_show_id, "event_title": "Booked Show"}
    booking_check = {"count": 4}

    with patch("app.services.show_service.get_show_by_id", new=AsyncMock(return_value=fake_show)), \
         patch("app.services.show_service.fetch_one", new=AsyncMock(return_value=booking_check)):
        res = client.delete(f"/api/manager/shows/{fake_show_id}")
        assert res.status_code == 400
        assert "active customer bookings" in res.json()["detail"].lower()
