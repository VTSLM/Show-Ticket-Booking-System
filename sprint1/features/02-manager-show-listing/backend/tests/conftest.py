import pytest
from starlette.testclient import TestClient
from app.main import app
from app.auth import ManagerUser, get_current_manager

@pytest.fixture
def mock_manager():
    return ManagerUser(
        id="a1111111-1111-1111-1111-111111111111",
        firebase_uid="DEV_FIREBASE_UID_MANAGER",
        name="Demo Manager",
        email="manager@example.com",
        status="active",
        roles=["manager"],
    )

@pytest.fixture
def client(mock_manager):
    app.dependency_overrides[get_current_manager] = lambda: mock_manager
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def unauth_client():
    with TestClient(app) as test_client:
        yield test_client
