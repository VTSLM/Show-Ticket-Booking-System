import pytest
from unittest.mock import AsyncMock

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

    assert result == rows

    query = conn.fetch.call_args.args[0]

    assert "s.status='scheduled'" in query
    assert "e.status='published'" in query
    assert "s.start_time > now()" in query
    assert "ORDER BY s.start_time ASC" in query
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

    assert "e.event_type = $1" in query
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
async def test_browse_shows_search_matches_title_or_venue():
    conn = make_conn()

    await browse_shows(
        city=None,
        event_type=None,
        language=None,
        search="imax",
        date=None,
        conn=conn,
    )

    query, *params = conn.fetch.call_args.args

    assert "(lower(e.title) LIKE lower($1) OR lower(v.name) LIKE lower($1))" in query
    assert params == ["%imax%"]


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

    assert "date(s.start_time) = $1::date" in query
    assert params == ["2026-11-15"]


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
    assert "e.event_type = $2" in query
    assert "lower(e.language) = lower($3)" in query
    assert "(lower(e.title) LIKE lower($4) OR lower(v.name) LIKE lower($4))" in query
    assert "date(s.start_time) = $5::date" in query

    assert params == [
        "Ahmedabad",
        "movie",
        "English",
        "%imax%",
        "2026-11-15",
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

    assert result == row
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
async def test_list_event_types_returns_event_types():
    conn = make_conn(
        fetch_rows=[
            {"event_type": "movie"},
            {"event_type": "concert"},
        ]
    )

    result = await list_event_types(conn=conn)

    assert result == ["movie", "concert"]