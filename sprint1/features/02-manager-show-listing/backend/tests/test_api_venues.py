from unittest.mock import AsyncMock, patch
import pytest

def test_create_venue_with_screens(client):
    fake_venue_id = "v1111111-2222-3333-4444-555555555555"
    fake_venue_row = {
        "id": fake_venue_id,
        "name": "PVR ICON: Gold Cinema",
        "address": "4th Floor, Nexus Mall",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560001",
    }
    fake_screen_row = {
        "id": "s1111111-2222-3333-4444-555555555555",
        "venue_id": fake_venue_id,
        "name": "Audi 1 (IMAX)",
        "capacity": 250,
        "created_at": None,
    }

    with patch("app.routers.venues.fetch_one", side_effect=[fake_venue_row, fake_screen_row]):
        payload = {
            "name": "PVR ICON: Gold Cinema",
            "address": "4th Floor, Nexus Mall",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
            "screens": [
                {"name": "Audi 1 (IMAX)", "capacity": 250}
            ],
        }
        res = client.post("/api/manager/venues", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "PVR ICON: Gold Cinema"
        assert data["city"] == "Bengaluru"
        assert len(data["screens"]) == 1
        assert data["screens"][0]["name"] == "Audi 1 (IMAX)"
        assert data["screens"][0]["capacity"] == 250

def test_create_venue_validation(client):
    # Missing required city
    res = client.post("/api/manager/venues", json={"name": "Cinema Only"})
    assert res.status_code == 422

    # Screen with invalid 0 capacity
    payload = {
        "name": "INOX Megaplex",
        "city": "Mumbai",
        "screens": [{"name": "Audi 1", "capacity": 0}],
    }
    res = client.post("/api/manager/venues", json=payload)
    assert res.status_code == 422

def test_create_venue_screen(client):
    fake_venue_id = "v1111111-2222-3333-4444-555555555555"
    venue_check = {"id": fake_venue_id}
    fake_screen = {
        "id": "s2222222-2222-3333-4444-555555555555",
        "venue_id": fake_venue_id,
        "name": "Audi 2 (4DX)",
        "capacity": 120,
        "created_at": None,
    }

    with patch("app.routers.venues.fetch_one", side_effect=[venue_check, fake_screen]):
        payload = {"name": "Audi 2 (4DX)", "capacity": 120}
        res = client.post(f"/api/manager/venues/{fake_venue_id}/screens", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Audi 2 (4DX)"
        assert data["capacity"] == 120

def test_delete_venue_success(client):
    fake_venue_id = "v1111111-2222-3333-4444-555555555555"
    venue_check = {"id": fake_venue_id, "name": "PVR Forum"}
    booking_check = {"count": 0}

    with patch("app.routers.venues.fetch_one", side_effect=[venue_check, booking_check]), \
         patch("app.routers.venues.execute", new_callable=AsyncMock) as mock_exec:
        res = client.delete(f"/api/manager/venues/{fake_venue_id}")
        assert res.status_code == 200
        assert res.json()["message"] == "Cinema venue deleted successfully"
        assert mock_exec.call_count == 5

def test_delete_venue_with_bookings_fails(client):
    fake_venue_id = "v1111111-2222-3333-4444-555555555555"
    venue_check = {"id": fake_venue_id, "name": "PVR Forum"}
    booking_check = {"count": 3}

    with patch("app.routers.venues.fetch_one", side_effect=[venue_check, booking_check]):
        res = client.delete(f"/api/manager/venues/{fake_venue_id}")
        assert res.status_code == 400
        assert "active bookings" in res.json()["detail"].lower()
