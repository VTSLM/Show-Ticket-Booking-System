from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.browse import (
    browse_shows,
    get_show_details,
    list_cities,
    list_event_types,
)


def make_conn(fetch_rows=None, fetchrow_result=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    return conn


@pytest.mark.asyncio
async def test_browse_shows_returns_scheduled_published_future_shows():
    rows = [
        {
            "show_id": "show-1",
            "title": "Movie A",
            "event_type": "movie",
            "language": "English",
            "venue_name": "Venue A",
            "city": "Ahmedabad",
            "available_seats": 50,
        }
    ]

    conn = make_conn(fetch_rows=rows)

    result = await browse_shows(
        city=None,
        event_type=None,
        language=None,
        search=None,
        date=None,
        conn=conn,
    )

    assert result == [
        {
            **rows[0],
            "current_price": None,
            "price_change_pct": 0,
            "pricing_reasons": [],
            "avg_rating": None,
            "review_count": 0,
        }
    ]

    query = conn.fetch.call_args.args[0]

    assert "s.status='scheduled'" in query
    assert "e.status='published'" in query
    assert "s.start_time > now()" in query
    assert "ORDER BY MIN(s.start_time) ASC" in query
    assert "LIMIT 100" in query


@pytest.mark.asyncio
async def test_browse_shows_city_filter_is_case_insensitive():
    conn = make_conn()

    await browse_shows(
        city="Ahmedabad",
        event_type=None,
        language=None,
        search=None,
        date=None,
        conn=conn,
    )

    query, *params = conn.fetch.call_args.args

    assert "lower(v.city) = lower($1)" in query
    assert params == ["Ahmedabad"]


@pytest.mark.asyncio
async def test_browse_shows_event_type_filter():
    conn = make_conn()

    await browse_shows(
        city=None,
        event_type="movie",
        language=None,
        search=None,
        date=None,
        conn=conn,
    )

    query, *params = conn.fetch.call_args.args

    assert "lower(e.event_type::text) = lower($1)" in query
    assert params == ["movie"]


@pytest.mark.asyncio
async def test_browse_shows_language_filter_is_case_insensitive():
    conn = make_conn()

    await browse_shows(
        city=None,
        event_type=None,
        language="English",
        search=None,
        date=None,
        conn=conn,
    )

    query, *params = conn.fetch.call_args.args

    assert "lower(e.language) = lower($1)" in query
    assert params == ["English"]


@pytest.mark.asyncio
async def test_browse_shows_search_matches_title_typos_or_venue():
    start_time = datetime(2026, 11, 20, 18, tzinfo=timezone.utc)
    conn = make_conn(fetch_rows=[
        {"show_id": "movie-1", "title": "Interstellar", "venue_name": "Cinema", "start_time": start_time},
        {"show_id": "movie-2", "title": "Drama", "venue_name": "Interstelar Cinema", "start_time": start_time},
        {"show_id": "movie-3", "title": "Oppenheimer", "venue_name": "Auditorium", "start_time": start_time},
    ])

    result = await browse_shows(
        city=None,
        event_type=None,
        language=None,
        search="Interstelar",
        date=None,
        sort_by="time_asc",
        conn=conn,
    )

    assert [show["show_id"] for show in result] == ["movie-2", "movie-1"]
    assert result[0]["relevance"] == 1
    assert 0 < result[1]["relevance"] < 1


@pytest.mark.asyncio
async def test_browse_shows_date_filter():
    conn = make_conn()

    await browse_shows(
        city=None,
        event_type=None,
        language=None,
        search=None,
        date="2026-11-15",
        conn=conn,
    )

    query, *params = conn.fetch.call_args.args

    assert "date(s.start_time) = $1" in query
    assert params == [date(2026, 11, 15)]


@pytest.mark.asyncio
async def test_browse_shows_combines_multiple_filters_in_order():
    conn = make_conn()

    await browse_shows(
        city="Ahmedabad",
        event_type="movie",
        language="English",
        search="imax",
        date="2026-11-15",
        conn=conn,
    )

    query, *params = conn.fetch.call_args.args

    assert "lower(v.city) = lower($1)" in query
    assert "lower(e.event_type::text) = lower($2)" in query
    assert "lower(e.language) = lower($3)" in query
    assert "date(s.start_time) = $4" in query

    assert params == [
        "Ahmedabad",
        "movie",
        "English",
        date(2026, 11, 15),
    ]


@pytest.mark.asyncio
async def test_browse_shows_returns_empty_list_when_no_matches():
    conn = make_conn(fetch_rows=[])

    result = await browse_shows(
        city=None,
        event_type=None,
        language=None,
        search="does-not-exist",
        date=None,
        conn=conn,
    )

    assert result == []


@pytest.mark.asyncio
async def test_get_show_details_returns_show():
    row = {
        "show_id": "show-1",
        "title": "Movie A",
        "event_type": "movie",
        "venue_name": "Venue A",
        "city": "Ahmedabad",
        "available_seats": 42,
        "total_seats": 100,
    }

    conn = make_conn(fetchrow_result=row)

    result = await get_show_details("show-1", conn=conn)

    assert {key: result[key] for key in row} == row
    assert result["is_default_terms"]
    assert result["terms_and_conditions"]
    assert result["terms_hash"]
    assert result["avg_rating"] is None
    assert result["review_count"] == 0
    assert result["zones"] == []
    assert result["upcoming_shows"] == []
    conn.fetchrow.assert_awaited_once()
    assert conn.fetchrow.call_args.args[1] == "show-1"


@pytest.mark.asyncio
async def test_get_show_details_returns_404_for_unknown_show():
    conn = make_conn(fetchrow_result=None)

    with pytest.raises(HTTPException) as exc:
        await get_show_details("missing-show", conn=conn)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Show not found"


@pytest.mark.asyncio
async def test_list_cities_returns_cities():
    conn = make_conn(
        fetch_rows=[
            {"city": "Ahmedabad"},
            {"city": "Mumbai"},
        ]
    )

    result = await list_cities(conn=conn)

    assert result == ["Ahmedabad", "Mumbai"]


@pytest.mark.asyncio
async def test_list_cities_only_counts_bookable_shows():
    """Venues with no upcoming published shows (test or half-made venues) are not listed."""
    conn = make_conn(fetch_rows=[])

    await list_cities(conn=conn)

    sql = conn.fetch.call_args.args[0]
    assert "JOIN shows s" in sql and "JOIN events e" in sql
    assert "s.status = 'scheduled'" in sql
    assert "e.status = 'published'" in sql
    assert "s.start_time > now()" in sql


@pytest.mark.asyncio
async def test_list_event_types_returns_event_types():
    conn = make_conn(
        fetch_rows=[
            {"event_type": "movie"},
            {"event_type": "concert"},
        ]
    )

    result = await list_event_types(conn=conn)

    assert result == ["movie", "concert"]
