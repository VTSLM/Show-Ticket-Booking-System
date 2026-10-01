import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.api.deps import get_location_service, get_show_service
from app.core.exceptions import NotFoundError
from app.main import app
from app.models.enums import EventType, ShowStatus
from app.schemas.common import Page
from app.schemas.location import CityOut
from app.schemas.show import EventSummary, ShowListItem, VenueSummary

NOW = datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc)


def _item() -> ShowListItem:
    return ShowListItem(
        id=uuid.uuid4(), start_time=NOW, end_time=NOW, status=ShowStatus.SCHEDULED,
        event=EventSummary(id=uuid.uuid4(), title="Interstellar", event_type=EventType.MOVIE),
        venue=VenueSummary(id=uuid.uuid4(), name="PVR", address="x", city="Gandhinagar", state="Gujarat", pincode="382011"),
        screen_name="Screen 1", min_price=Decimal("200"), max_price=Decimal("600"),
        currency="INR", available_seats=10, is_sold_out=False,
    )


class FakeShowService:
    last_kwargs: dict = {}

    async def list_shows(self, **kwargs):
        FakeShowService.last_kwargs = kwargs
        return Page[ShowListItem](items=[_item()], total=1, page=1, page_size=20, total_pages=1)

    async def get_show_details(self, show_id):
        raise NotFoundError("Show not found")


class FakeLocationService:
    async def list_cities(self, search=None):
        return [CityOut(city="Gandhinagar", state="Gujarat", show_count=3)]


async def test_liveness(client):
    r = await client.get("/health")
    assert r.status_code == 200


async def test_cities(client):
    app.dependency_overrides[get_location_service] = lambda: FakeLocationService()
    r = await client.get("/api/v1/locations/cities")
    assert r.status_code == 200
    assert r.json()[0]["city"] == "Gandhinagar"


async def test_nearby_requires_city(client):
    r = await client.get("/api/v1/shows")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_nearby_shows(client):
    app.dependency_overrides[get_show_service] = lambda: FakeShowService()
    r = await client.get("/api/v1/shows", params={"city": "Gandhinagar"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert FakeShowService.last_kwargs["city"] == "Gandhinagar"


async def test_search_passes_query(client):
    app.dependency_overrides[get_show_service] = lambda: FakeShowService()
    r = await client.get("/api/v1/shows/search", params={"q": "inter"})
    assert r.status_code == 200
    assert FakeShowService.last_kwargs["query"] == "inter"


async def test_show_not_found(client):
    app.dependency_overrides[get_show_service] = lambda: FakeShowService()
    r = await client.get(f"/api/v1/shows/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
