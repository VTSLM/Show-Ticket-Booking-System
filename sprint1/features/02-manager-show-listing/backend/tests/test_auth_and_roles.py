from unittest.mock import AsyncMock, patch

def test_unauthenticated_request_fails(unauth_client):
    response = unauth_client.get("/api/manager/events")
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json()["detail"]

def test_customer_role_forbidden(unauth_client):
    headers = {"X-Dev-Firebase-Uid": "DEV_FIREBASE_UID_CUSTOMER"}
    with patch("app.auth.get_settings") as mock_settings:
        mock_settings.return_value.DEV_BYPASS_AUTH = True
        mock_settings.return_value.DATABASE_URL = "postgres://..."

        user_row = {
            "id": "c1111111-1111-1111-1111-111111111111",
            "firebase_uid": "DEV_FIREBASE_UID_CUSTOMER",
            "name": "Normal Customer",
            "email": "cust@example.com",
            "status": "active",
            "roles": ["customer"],
        }
        with patch("app.auth.get_db_pool", new=AsyncMock(return_value=object())):
            with patch("app.auth.fetch_one", new=AsyncMock(return_value=user_row)):
                response = unauth_client.get("/api/manager/events", headers=headers)
                assert response.status_code == 403
                assert "manager permissions" in response.json()["detail"]

def test_manager_role_authorized(unauth_client):
    headers = {"X-Dev-Firebase-Uid": "DEV_FIREBASE_UID_MANAGER"}
    with patch("app.auth.get_settings") as mock_settings:
        mock_settings.return_value.DEV_BYPASS_AUTH = True
        mock_settings.return_value.DATABASE_URL = "postgres://..."

        user_row = {
            "id": "m1111111-1111-1111-1111-111111111111",
            "firebase_uid": "DEV_FIREBASE_UID_MANAGER",
            "name": "Demo Manager",
            "email": "mgr@example.com",
            "status": "active",
            "roles": ["manager"],
        }
        with patch("app.auth.get_db_pool", new=AsyncMock(return_value=object())):
            with patch("app.auth.fetch_one", new=AsyncMock(return_value=user_row)):
                with patch("app.services.event_service.fetch_all", new=AsyncMock(return_value=[])):
                    response = unauth_client.get("/api/manager/events", headers=headers)
                    assert response.status_code == 200
