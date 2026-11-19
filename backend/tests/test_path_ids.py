"""Malformed ids in URLs return 404 before any database query (#140)."""
import re
import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from database import get_conn
from main import app
from path_ids import is_uuid, validate_path_ids

PARAM = re.compile(r"{([^}:]+)(?::[^}]*)?}")


def _id_routes():
    """(method, path template) for every route with an ``*_id`` path parameter.

    Read from the OpenAPI schema: newer FastAPI versions keep included routers
    as nested objects, so ``app.routes`` no longer lists every route.
    """
    out = []
    for path, operations in app.openapi()["paths"].items():
        if any(p.endswith("_id") for p in PARAM.findall(path)):
            for method in sorted(operations):
                out.append((method.upper(), path))
    return out


ID_ROUTES = _id_routes()


@pytest.fixture
def client_without_db():
    """The database must never be reached for a malformed id."""
    conn = MagicMock()
    conn.fetchrow.side_effect = AssertionError("database was queried")
    conn.fetch.side_effect = AssertionError("database was queried")
    conn.fetchval.side_effect = AssertionError("database was queried")
    conn.execute.side_effect = AssertionError("database was queried")

    async def fake_conn():
        yield conn

    app.dependency_overrides[get_conn] = fake_conn
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_conn, None)


def test_routes_with_ids_were_found():
    # Guards the parametrised test below against silently testing nothing
    assert len(ID_ROUTES) > 40
    assert ("GET", "/api/seats/{show_id}/map") in ID_ROUTES


@pytest.mark.parametrize("method,template", ID_ROUTES)
def test_malformed_id_returns_404_without_database(client_without_db, method, template):
    path = PARAM.sub(
        lambda m: "not-a-uuid" if m.group(1).endswith("_id") else "x", template
    )
    r = client_without_db.request(method, path, headers={"Authorization": "Bearer whatever"})
    assert r.status_code == 404, f"{method} {path} -> {r.status_code} {r.text}"
    assert r.json() == {"detail": "Not found"}


def test_issue_example_without_login(client_without_db):
    r = client_without_db.get("/api/seats/not-a-uuid/map")
    assert r.status_code == 404


@pytest.mark.parametrize("bad", ["not-a-uuid", "1", "' OR 1=1 --", "123e4567-e89b-12d3-a456-42661417400"])
def test_is_uuid_rejects_bad_values(bad):
    assert not is_uuid(bad)


def test_is_uuid_accepts_uuid():
    assert is_uuid(str(uuid.uuid4()))


def _request(path_params):
    req = MagicMock()
    req.path_params = path_params
    return req


@pytest.mark.asyncio
async def test_valid_ids_pass():
    await validate_path_ids(_request({"show_id": str(uuid.uuid4()), "booking_id": str(uuid.uuid4())}))


@pytest.mark.asyncio
async def test_non_id_params_are_not_checked():
    # e.g. /api/payments/receipts/{receipt_number}
    await validate_path_ids(_request({"receipt_number": "RCPT-2026-0001"}))


@pytest.mark.asyncio
async def test_one_bad_id_among_good_ones_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await validate_path_ids(_request({"case_id": str(uuid.uuid4()), "document_id": "nope"}))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_seat_map_of_unknown_show_returns_404():
    # A well-formed id that matches no show used to return an empty seat map with 200
    from unittest.mock import AsyncMock
    from routers.seats import get_seat_map

    conn = AsyncMock()
    conn.fetchrow.return_value = None
    with pytest.raises(HTTPException) as exc:
        await get_seat_map(show_id=str(uuid.uuid4()), conn=conn)
    assert exc.value.status_code == 404
    conn.execute.assert_not_called()  # no lock cleanup for a show that does not exist
