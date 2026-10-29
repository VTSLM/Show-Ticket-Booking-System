from unittest.mock import AsyncMock, patch

def test_seat_count_from_physical_seats(client):
    screen_id = "s1111111-1111-1111-1111-111111111111"
    screen_row = {
        "id": screen_id,
        "venue_id": "v1111111-1111-1111-1111-111111111111",
        "screen_name": "Screen 1",
        "capacity": 50,
        "venue_name": "Grand Cinema",
    }
    seats_row = {"seat_count": 48}

    with patch("app.services.seat_service.fetch_one", new=AsyncMock()) as mock_fetch:
        mock_fetch.side_effect = [screen_row, seats_row, None]

        response = client.get(f"/api/manager/screens/{screen_id}/seat-count")
        assert response.status_code == 200
        data = response.json()
        assert data["seat_count"] == 48
        assert data["source"] == "seats_table"
        assert data["screen_capacity"] == 50

def test_seat_count_fallback_to_screen_capacity(client):
    screen_id = "s1111111-1111-1111-1111-111111111111"
    screen_row = {
        "id": screen_id,
        "venue_id": "v1111111-1111-1111-1111-111111111111",
        "screen_name": "Screen 2",
        "capacity": 75,
        "venue_name": "Grand Cinema",
    }
    seats_row = {"seat_count": 0}

    with patch("app.services.seat_service.fetch_one", new=AsyncMock()) as mock_fetch:
        mock_fetch.side_effect = [screen_row, seats_row, None]

        response = client.get(f"/api/manager/screens/{screen_id}/seat-count")
        assert response.status_code == 200
        data = response.json()
        assert data["seat_count"] == 75
        assert data["source"] == "screens_capacity"
