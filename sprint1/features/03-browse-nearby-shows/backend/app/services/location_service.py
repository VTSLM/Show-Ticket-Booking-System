from app.repositories.location_repository import LocationRepository
from app.schemas.location import CityOut


class LocationService:
    def __init__(self, repo: LocationRepository):
        self.repo = repo

    async def list_cities(self, search: str | None = None) -> list[CityOut]:
        rows = await self.repo.list_cities(search)
        return [CityOut(city=r.city, state=r.state, show_count=r.show_count) for r in rows]
