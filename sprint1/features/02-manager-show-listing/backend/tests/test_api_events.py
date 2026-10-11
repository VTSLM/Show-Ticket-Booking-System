from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

def test_create_valid_event(client):
    fake_created = {
        "id": "e1111111-1111-1111-1111-111111111111",
        "title": "Inception 2",
        "description": "Mind-bending sequel",
        "event_type": "movie",
        "duration_minutes": 148,
        "language": "English",
        "genre": "Sci-Fi",
        "poster_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
        "status": "draft",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    with patch("app.services.event_service.fetch_one", new=AsyncMock(return_value=fake_created)):
        response = client.post(
            "/api/manager/events",
            json={
                "title": "Inception 2",
                "description": "Mind-bending sequel",
                "event_type": "movie",
                "duration_minutes": 148,
                "language": "English",
                "genre": "Sci-Fi",
                "poster_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "status": "draft",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "e1111111-1111-1111-1111-111111111111"
        assert data["title"] == "Inception 2"
        assert data["event_type"] == "movie"
        assert data["poster_url"] == "https://res.cloudinary.com/demo/image/upload/sample.jpg"

def test_create_event_missing_title(client):
    response = client.post(
        "/api/manager/events",
        json={
            "description": "No title provided",
            "event_type": "movie",
        },
    )
    assert response.status_code == 422

def test_create_event_invalid_enum(client):
    response = client.post(
        "/api/manager/events",
        json={
            "title": "Invalid Type Show",
            "event_type": "circus_not_in_enum",
        },
    )
    assert response.status_code == 422

def test_list_manager_events(client):
    fake_list = [
        {
            "id": "e1111111-1111-1111-1111-111111111111",
            "title": "Demo Movie",
            "description": "A demo film",
            "event_type": "movie",
            "duration_minutes": 120,
            "language": "English",
            "genre": "Drama",
            "poster_url": None,
            "status": "published",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]
    with patch("app.services.event_service.fetch_all", new=AsyncMock(return_value=fake_list)):
        response = client.get("/api/manager/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Demo Movie"

def test_event_database_error_handling(client):
    with patch("app.services.event_service.fetch_one", new=AsyncMock(side_effect=Exception("Database connection timeout"))):
        response = client.post(
            "/api/manager/events",
            json={
                "title": "Failing Event",
                "event_type": "concert",
            },
        )
        assert response.status_code == 400
        assert "Database connection timeout" in response.json()["detail"]
