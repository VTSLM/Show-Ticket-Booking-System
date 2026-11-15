"""
Tests for Issue #57: Organizer and Venue Verification Guards.
Validates:
- Multi-organization support per user account.
- Manager event creation guard requiring approved organizer profile.
- Double-lock show scheduling guard (both Organizer AND Venue must be verified).
- Admin role override permissions.
"""

import pytest
import uuid
from unittest.mock import AsyncMock
from fastapi import HTTPException
from routers.manager import create_event, EventCreate, create_show, ShowCreate
from routers.organizer_verification import save_application_draft, ApplicationDraftRequest, BusinessType


@pytest.mark.asyncio
async def test_manager_cannot_create_event_without_approved_org():
    conn = AsyncMock()
    user_id = str(uuid.uuid4())
    manager_user = {"id": user_id, "role": "manager"}

    # Mock no approved organizations found
    conn.fetch.return_value = []

    body = EventCreate(title="Unauthorized Indie Music Fest", event_type="concert")

    with pytest.raises(HTTPException) as exc:
        await create_event(body=body, user=manager_user, conn=conn)

    assert exc.value.status_code == 403
    assert "Organizer verification required" in exc.value.detail


@pytest.mark.asyncio
async def test_manager_cannot_create_event_with_unapproved_org():
    conn = AsyncMock()
    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    manager_user = {"id": user_id, "role": "manager"}

    # Mock organization is currently PENDING review
    conn.fetchrow.return_value = {
        "id": org_id,
        "verification_status": "PENDING",
        "legal_name": "Pending Events LLP"
    }

    body = EventCreate(title="Summer Tour", event_type="concert", organizer_id=org_id)

    with pytest.raises(HTTPException) as exc:
        await create_event(body=body, user=manager_user, conn=conn)

    assert exc.value.status_code == 403
    assert "is not approved" in exc.value.detail


@pytest.mark.asyncio
async def test_manager_create_event_with_approved_org():
    conn = AsyncMock()
    user_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    manager_user = {"id": user_id, "role": "manager"}

    conn.fetchrow.side_effect = [
        # Check org
        {"id": org_id, "verification_status": "APPROVED", "legal_name": "Global Live LLC"},
        # Insert event
        {"id": event_id, "title": "Global Music Festival", "organizer_id": org_id, "status": "draft"}
    ]

    body = EventCreate(title="Global Music Festival", event_type="concert", organizer_id=org_id)
    res = await create_event(body=body, user=manager_user, conn=conn)

    assert res["id"] == event_id
    assert res["organizer_id"] == org_id


@pytest.mark.asyncio
async def test_create_show_blocked_when_organizer_unapproved():
    conn = AsyncMock()
    manager_user = {"id": str(uuid.uuid4()), "role": "manager"}
    screen_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())

    # Mock guard query: Venue is approved, but Organization is NOT approved
    conn.fetchrow.return_value = {
        "event_title": "Untrusted Rock Night",
        "organizer_id": str(uuid.uuid4()),
        "org_name": "Unverified Organizer",
        "org_status": "PENDING",
        "venue_name": "Narendra Modi Stadium",
        "venue_status": "approved"
    }

    body = ShowCreate(
        event_id=event_id,
        screen_id=screen_id,
        start_time="2027-01-01T18:00:00Z",
        end_time="2027-01-01T21:00:00Z",
        base_price=500.0
    )

    with pytest.raises(HTTPException) as exc:
        await create_show(body=body, user=manager_user, conn=conn)

    assert exc.value.status_code == 403
    assert "host organization 'Unverified Organizer' is not verified" in exc.value.detail


@pytest.mark.asyncio
async def test_create_show_blocked_when_venue_unverified():
    conn = AsyncMock()
    manager_user = {"id": str(uuid.uuid4()), "role": "manager"}
    screen_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())

    # Mock guard query: Organization is approved, but Venue is unverified
    conn.fetchrow.return_value = {
        "event_title": "Grand Concert",
        "organizer_id": str(uuid.uuid4()),
        "org_name": "Verified Live India",
        "org_status": "APPROVED",
        "venue_name": "Unregistered Basement Club",
        "venue_status": "unverified"
    }

    body = ShowCreate(
        event_id=event_id,
        screen_id=screen_id,
        start_time="2027-01-01T18:00:00Z",
        end_time="2027-01-01T21:00:00Z",
        base_price=500.0
    )

    with pytest.raises(HTTPException) as exc:
        await create_show(body=body, user=manager_user, conn=conn)

    assert exc.value.status_code == 403
    assert "Venue 'Unregistered Basement Club' is not verified" in exc.value.detail


@pytest.mark.asyncio
async def test_create_show_succeeds_when_both_verified():
    conn = AsyncMock()
    manager_user = {"id": str(uuid.uuid4()), "role": "manager"}
    screen_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    show_id = str(uuid.uuid4())

    # 1. Guard check: Both APPROVED
    # 2. Insert show
    conn.fetchrow.side_effect = [
        {
            "event_title": "Coldplay Live",
            "organizer_id": str(uuid.uuid4()),
            "org_name": "Live Nation India",
            "org_status": "APPROVED",
            "venue_name": "Narendra Modi Stadium",
            "venue_status": "approved"
        },
        {
            "id": show_id,
            "event_id": event_id,
            "screen_id": screen_id,
            "base_price": 3000.0,
            "status": "scheduled"
        }
    ]

    body = ShowCreate(
        event_id=event_id,
        screen_id=screen_id,
        start_time="2027-01-01T18:00:00Z",
        end_time="2027-01-01T21:00:00Z",
        base_price=3000.0
    )

    res = await create_show(body=body, user=manager_user, conn=conn)
    assert res["id"] == show_id
    assert conn.execute.called


@pytest.mark.asyncio
async def test_admin_bypasses_verification_guards():
    conn = AsyncMock()
    admin_user = {"id": str(uuid.uuid4()), "role": "admin"}
    screen_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    show_id = str(uuid.uuid4())

    # Admin skips guard check query directly to INSERT
    conn.fetchrow.return_value = {
        "id": show_id,
        "event_id": event_id,
        "screen_id": screen_id,
        "base_price": 100.0,
        "status": "scheduled"
    }

    body = ShowCreate(
        event_id=event_id,
        screen_id=screen_id,
        start_time="2027-01-01T18:00:00Z",
        end_time="2027-01-01T21:00:00Z",
        base_price=100.0
    )

    res = await create_show(body=body, user=admin_user, conn=conn)
    assert res["id"] == show_id

