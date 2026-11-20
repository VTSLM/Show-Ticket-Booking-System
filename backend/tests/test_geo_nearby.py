"""Shows near me: distance maths, city fallback, radius filter, browse wiring."""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from routers.browse import browse_shows, india_cities
from services.geo_service import (
    INDIA_CITIES, city_centroid, haversine_km, venue_point, venues_within,
)

AHMEDABAD = (23.0225, 72.5714)


def test_haversine_known_distances():
    assert haversine_km(*AHMEDABAD, *AHMEDABAD) == 0
    # Ahmedabad -> Mumbai is about 440 km in a straight line
    assert 430 < haversine_km(*AHMEDABAD, 19.0760, 72.8777) < 450
    # one degree of latitude is about 111 km
    assert 110.5 < haversine_km(10, 77, 11, 77) < 111.8


def test_city_names_and_aliases_resolve():
    assert city_centroid("Ahmedabad") == city_centroid("  ahmedabad ")
    assert city_centroid("Bangalore") == city_centroid("Bengaluru")
    assert city_centroid("Atlantis") is None
    assert city_centroid(None) is None


def test_city_list_has_valid_unique_points():
    names = [c["name"] for c in INDIA_CITIES]
    assert len(names) == len(set(names)) and len(names) > 100
    for c in INDIA_CITIES:
        assert 6 < c["lat"] < 38 and 67 < c["lng"] < 98, c["name"]  # inside India's bounding box


def test_venue_uses_own_coordinates_before_city_centre():
    exact = venue_point({"city": "Ahmedabad", "latitude": 23.1, "longitude": 72.6})
    assert exact == (23.1, 72.6, True)
    approx = venue_point({"city": "Ahmedabad", "latitude": None, "longitude": None})
    assert approx[2] is False and approx[:2] == AHMEDABAD
    assert venue_point({"city": "Atlantis"}) is None


def test_only_venues_inside_the_radius_are_returned_nearest_first():
    near, mid, far, unknown = uuid4(), uuid4(), uuid4(), uuid4()
    venues = [
        {"id": far, "city": "Surat"},
        {"id": mid, "city": "Gandhinagar"},
        {"id": near, "city": "Ahmedabad", "latitude": 23.03, "longitude": 72.58},
        {"id": unknown, "city": "Atlantis"},
    ]
    found = venues_within(venues, *AHMEDABAD, radius_km=100)
    assert [f["venue_id"] for f in found] == [near, mid]
    assert found[0]["exact"] is True and found[1]["exact"] is False
    assert 0 < found[0]["distance_km"] < 3


def _kwargs(**kw):
    base = dict(city=None, event_type=None, language=None, genre=None, search=None,
                date=None, sort_by="time_asc", lat=None, lng=None, radius_km=100)
    return {**base, **kw}


@pytest.mark.asyncio
async def test_browse_needs_both_lat_and_lng():
    with pytest.raises(HTTPException) as e:
        await browse_shows(**_kwargs(lat=23.0), conn=AsyncMock())
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_radius_applies_to_everything_except_concerts():
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"id": uuid4(), "city": "Surat", "latitude": None, "longitude": None}],  # venues
        [],                                                                        # shows
    ])
    assert await browse_shows(**_kwargs(lat=28.61, lng=77.20), conn=conn) == []
    sql = conn.fetch.await_args_list[1].args[0]
    params = conn.fetch.await_args_list[1].args[1:]
    assert "lower(e.event_type::text) = 'concert' OR nv.dist_km <=" in sql
    assert "LEFT JOIN unnest(" in sql  # concerts at unlocated venues still listed
    assert 100.0 in params


def test_venues_with_distance_keeps_far_venues_and_skips_unknown_places():
    from services.geo_service import venues_with_distance
    far, unknown = uuid4(), uuid4()
    got = venues_with_distance([{"id": far, "city": "Surat"}, {"id": unknown, "city": "Atlantis"}], *AHMEDABAD)
    assert [g["venue_id"] for g in got] == [far]
    assert got[0]["distance_km"] > 100


@pytest.mark.asyncio
async def test_browse_nearby_joins_distances_into_the_query():
    vid = uuid4()
    conn = AsyncMock()
    shows_row = {"event_id": uuid4(), "show_id": uuid4(), "title": "T", "venue_name": "V",
                 "start_time": None, "base_price": None, "dynamic_pricing": False,
                 "sold_seats": 0, "total_seats": 0, "distance_km": 12.3456, "distance_exact": True}
    conn.fetch = AsyncMock(side_effect=[
        [{"id": vid, "city": "Ahmedabad", "latitude": 23.03, "longitude": 72.58}],  # venues
        [shows_row],                                                                  # shows
        [],                                                                           # ratings
    ])
    result = await browse_shows(**_kwargs(lat=23.0225, lng=72.5714, sort_by="distance_asc"), conn=conn)
    sql = conn.fetch.await_args_list[1].args[0]
    assert "unnest($1::uuid[], $2::float8[], $3::boolean[])" in sql
    assert "nv.dist_km" in sql
    assert result[0]["distance_km"] == 12.35 and result[0]["distance_exact"] is True


@pytest.mark.asyncio
async def test_india_cities_endpoint_lists_cities():
    cities = await india_cities()
    assert {"name", "state", "lat", "lng"} <= set(cities[0])
