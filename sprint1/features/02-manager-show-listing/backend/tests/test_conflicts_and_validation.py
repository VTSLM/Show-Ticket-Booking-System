from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

def test_scheduling_conflict_detected(client):
    start = datetime.now(timezone.utc) + timedelta(days=1, hours=10)
    end = start + timedelta(hours=3)

    event_row = {"id": "e1111111-1111-1111-1111-111111111111", "title": "Movie A", "duration_minutes": 120}
    screen_row = {"id": "s1111111-1111-1111-1111-111111111111", "venue_id": "v1111111-1111-1111-1111-111111111111", "name": "Screen 1", "capacity": 50}

    with patch("app.services.show_service.fetch_one", new=AsyncMock()) as mock_fetch:
        mock_fetch.side_effect = [event_row, screen_row, {"id": "existing-show-uuid"}]

        response = client.post(
            "/api/manager/shows",
            json={
                "event_id": event_row["id"],
                "screen_id": screen_row["id"],
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert response.status_code == 409
        assert "Scheduling conflict" in response.json()["detail"]
