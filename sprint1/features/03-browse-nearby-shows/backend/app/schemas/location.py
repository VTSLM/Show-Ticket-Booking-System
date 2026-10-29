from pydantic import BaseModel


class CityOut(BaseModel):
    city: str
    state: str
    show_count: int
