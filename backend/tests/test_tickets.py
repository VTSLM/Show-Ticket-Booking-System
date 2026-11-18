from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from database import get_conn
from dependencies import get_current_user
from routers.tickets import (
    router,
    SCANNER_ROLES,
    verify_ticket,
    scan_ticket,
    scan_ticket_by_booking_id,
    TicketScanRequest,
)

SAMPLE_BOOKING_ID = "408e08d1-d2f6-4d0f-a9cb-b295f70a7b45"
SAMPLE_TICKET_ID = "99999999-9999-9999-9999-999999999999"

OWNER_MANAGER = {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Show Manager",
    "email": "manager@org.com",
    "roles": ["manager"],
}

OTHER_MANAGER = {
    "id": "22222222-2222-2222-2222-222222222222",
    "name": "Other Manager",
    "email": "other@otherorg.com",
    "roles": ["manager"],
}

ADMIN_USER = {
    "id": "33333333-3333-3333-3333-333333333333",
    "name": "Super Admin",
    "email": "admin@ticketflow.com",
    "roles": ["admin"],
}

CUSTOMER_USER = {
    "id": "44444444-4444-4444-4444-444444444444",
    "name": "Regular Customer",
    "email": "customer@gmail.com",
    "roles": ["customer"],
}


def make_conn(fetch_rows=None, fetchrow_result=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_result)
    return conn


def _make_ticket_row(is_owner=True, is_used=False, status="valid"):
    return {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": status,
        "is_used": is_used,
        "event_title": "Inception (Re-release)",
        "start_time": "2026-11-17 08:15:00+00",
        "venue_name": "PVR Icon",
        "screen_name": "Audi 1",
        "user_name": "Rahul Sharma",
        "user_email": "rahul@example.com",
        "is_owner": is_owner,
    }


# ---------------------------------------------------------------------------
# 1. Route Security & Role Checks
# ---------------------------------------------------------------------------

def test_scan_endpoints_require_scanner_roles_dependency():
    """Both scan endpoints must be protected with SCANNER_ROLES (manager, admin)."""
    scan_paths = {"/api/tickets/scan", "/api/tickets/bookings/{booking_id}/scan"}
    found = 0
    for r in router.routes:
        if isinstance(r, APIRoute) and r.path in scan_paths:
            calls = [d.call for d in r.dependant.dependencies]
            assert SCANNER_ROLES in calls, f"{r.path} is missing SCANNER_ROLES dependency"
            found += 1
    assert found == 2


def test_scan_without_token_returns_401():
    """Requests without an Authorization header are rejected with 401."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: None
    client = TestClient(app)

    res = client.post("/api/tickets/scan", json={"booking_id": SAMPLE_BOOKING_ID})
    assert res.status_code == 401
    assert res.json()["detail"] == "Not authenticated"


def test_scan_with_customer_role_returns_403():
    """Customers attempting to access scan endpoints must receive 403 Forbidden."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_conn] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: CUSTOMER_USER
    client = TestClient(app)

    res = client.post("/api/tickets/scan", json={"booking_id": SAMPLE_BOOKING_ID})
    assert res.status_code == 403
    assert "Requires one of roles" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 2. Organization Ownership & Scan Admission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_of_another_venue_or_organization_gets_404():
    """A manager from another venue or organization must receive 404 (does not confirm ticket existence)."""
    ticket_row = _make_ticket_row(is_owner=False)
    conn = make_conn(fetchrow_result=ticket_row)

    req = TicketScanRequest(booking_id=SAMPLE_BOOKING_ID)
    with pytest.raises(HTTPException) as exc_info:
        await scan_ticket(body=req, current_user=OTHER_MANAGER, conn=conn)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Ticket not found for this booking"


@pytest.mark.asyncio
async def test_venue_manager_can_scan_and_admit_200():
    """The manager who owns the venue can scan and admit the ticket."""
    ticket_row = _make_ticket_row(is_owner=True, is_used=False, status="valid")
    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_row, consumed_row])

    req = TicketScanRequest(qr_data=f"TICKETFLOW:{SAMPLE_BOOKING_ID}")
    result = await scan_ticket(body=req, current_user=OWNER_MANAGER, conn=conn)

    assert result["success"] is True
    assert result["valid"] is True
    assert result["status"] == "used"
    assert result["used"] is True
    assert result["attendee"]["name"] == "Rahul Sharma"
    assert result["attendee"]["email"] == "rahul@example.com"
    assert result["event"]["title"] == "Inception (Re-release)"
    assert "01:45 PM" in result["event"]["start_time"]


@pytest.mark.asyncio
async def test_shows_own_manager_can_scan_and_admit_200():
    """The manager who owns the show's organization can scan and admit the ticket."""
    ticket_row = _make_ticket_row(is_owner=True, is_used=False, status="valid")
    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_row, consumed_row])

    req = TicketScanRequest(qr_data=f"TICKETFLOW:{SAMPLE_BOOKING_ID}")
    result = await scan_ticket(body=req, current_user=OWNER_MANAGER, conn=conn)

    assert result["success"] is True
    assert result["valid"] is True
    assert result["status"] == "used"
    assert result["used"] is True
    assert result["attendee"]["name"] == "Rahul Sharma"
    assert result["attendee"]["email"] == "rahul@example.com"
    assert result["event"]["title"] == "Inception (Re-release)"
    assert "01:45 PM" in result["event"]["start_time"]


@pytest.mark.asyncio
async def test_admin_can_scan_any_organizations_ticket_200():
    """Admins bypass organization ownership checks and can scan any show's ticket."""
    ticket_row = _make_ticket_row(is_owner=False, is_used=False, status="valid")
    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_row, consumed_row])

    req = TicketScanRequest(booking_id=SAMPLE_BOOKING_ID)
    result = await scan_ticket(body=req, current_user=ADMIN_USER, conn=conn)

    assert result["success"] is True
    assert result["status"] == "used"


@pytest.mark.asyncio
async def test_second_scan_rejects_already_used_ticket_409():
    """Subsequent scan attempts on an already-used ticket must be rejected with 409 Conflict."""
    ticket_row = _make_ticket_row(is_owner=True, is_used=True, status="used")
    conn = make_conn(fetchrow_result=ticket_row)

    req = TicketScanRequest(booking_id=SAMPLE_BOOKING_ID)
    with pytest.raises(HTTPException) as exc_info:
        await scan_ticket(body=req, current_user=OWNER_MANAGER, conn=conn)

    assert exc_info.value.status_code == 409
    assert "already been scanned and used" in exc_info.value.detail
    assert "Duplicate entry is not permitted" in exc_info.value.detail


@pytest.mark.asyncio
async def test_scan_ticket_rejects_cancelled_ticket_400():
    """Cancelled tickets must be rejected with 400 Bad Request."""
    ticket_row = _make_ticket_row(is_owner=True, is_used=False, status="cancelled")
    conn = make_conn(fetchrow_result=ticket_row)

    req = TicketScanRequest(booking_id=SAMPLE_BOOKING_ID)
    with pytest.raises(HTTPException) as exc_info:
        await scan_ticket(body=req, current_user=OWNER_MANAGER, conn=conn)

    assert exc_info.value.status_code == 400
    assert "cancelled" in exc_info.value.detail


@pytest.mark.asyncio
async def test_scan_ticket_by_booking_id_endpoint():
    """Path parameter endpoint /bookings/{booking_id}/scan works with authorization."""
    ticket_row = _make_ticket_row(is_owner=True, is_used=False, status="valid")
    consumed_row = {
        "id": SAMPLE_TICKET_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "status": "used",
        "is_used": True,
    }

    conn = AsyncMock()
    conn.fetchrow = AsyncMock(side_effect=[ticket_row, consumed_row])

    result = await scan_ticket_by_booking_id(
        booking_id=SAMPLE_BOOKING_ID,
        current_user=OWNER_MANAGER,
        conn=conn,
    )
    assert result["success"] is True
    assert result["used"] is True
    assert result["status"] == "used"


# ---------------------------------------------------------------------------
# 3. Public Verify Endpoint (Strictly GET & Minimal - No PII)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_public_verify_returns_minimal_info_without_name_or_email():
    """Public GET verify must be minimal and never return attendee name or email."""
    conn = make_conn(fetchrow_result={
        "id": SAMPLE_TICKET_ID,
        "status": "valid",
        "is_used": False,
    })

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, conn=conn)

    assert result["valid"] is True
    assert result["used"] is False
    assert result["status"] == "valid"
    assert result["ticket_id"] == SAMPLE_TICKET_ID
    assert "ready for entry" in result["message"]

    # Verify no PII leak in public response
    assert "name" not in result
    assert "email" not in result
    assert "attendee" not in result
    assert "user_name" not in result
    assert "user_email" not in result


@pytest.mark.asyncio
async def test_verify_ticket_invalid_id_format():
    conn = make_conn()
    result = await verify_ticket(booking_id="not-a-valid-uuid", conn=conn)

    assert result["valid"] is False
    assert "Invalid ticket ID format" in result["message"]


@pytest.mark.asyncio
async def test_verify_ticket_not_found():
    conn = make_conn(fetchrow_result=None)
    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, conn=conn)

    assert result["valid"] is False
    assert result["message"] == "Ticket not found"


@pytest.mark.asyncio
async def test_verify_ticket_already_used():
    conn = make_conn(fetchrow_result={
        "id": SAMPLE_TICKET_ID,
        "status": "used",
        "is_used": True,
    })

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, conn=conn)

    assert result["valid"] is False
    assert result["used"] is True
    assert result["status"] == "used"
    assert "already" in result["message"].lower()


@pytest.mark.asyncio
async def test_verify_ticket_cancelled():
    conn = make_conn(fetchrow_result={
        "id": SAMPLE_TICKET_ID,
        "status": "cancelled",
        "is_used": False,
    })

    result = await verify_ticket(booking_id=SAMPLE_BOOKING_ID, conn=conn)

    assert result["valid"] is False
    assert result["status"] == "cancelled"
    assert "cancelled" in result["message"]
