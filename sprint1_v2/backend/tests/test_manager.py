from datetime import datetime, timedelta, timezone
import pytest
import main as app_main
from dependencies import get_current_user


def test_man_001_create_venue_success(client):
    res = client.post(
        "/api/manager/venues",
        json={"name": "PVR Inox Wave", "city": "Gandhinagar", "address": "Sector 1"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "PVR Inox Wave"
    assert res.json()["city"] == "Gandhinagar"


def test_man_002_create_venue_missing_mandatory_fields(client):
    res = client.post("/api/manager/venues", json={"address": "Street only"})
    assert res.status_code == 422


def test_man_003_create_screen_generates_seat_grid(client, fake_db):
    v = client.post("/api/manager/venues", json={"name": "Cineplex", "city": "Ahmedabad"}).json()
    res = client.post(
        f"/api/manager/venues/{v['id']}/screens",
        json={"name": "Audi 1", "capacity": 20, "rows": 2, "cols": 10},
    )
    assert res.status_code == 200
    screen_id = res.json()["id"]
    seats = [s for s in fake_db.seats.values() if str(s["screen_id"]) == screen_id]
    assert len(seats) == 20


def test_man_004_create_screen_capacity_only(client, fake_db):
    v = client.post("/api/manager/venues", json={"name": "Open Air", "city": "Surat"}).json()
    res = client.post(
        f"/api/manager/venues/{v['id']}/screens",
        json={"name": "Lawn", "capacity": 50},
    )
    assert res.status_code == 200
    screen_id = res.json()["id"]
    assert sum(1 for s in fake_db.seats.values() if str(s["screen_id"]) == screen_id) == 0


def test_man_005_create_event_defaults_to_draft(client):
    res = client.post(
        "/api/manager/events",
        json={"title": "Dune Part 3", "event_type": "movie", "duration_minutes": 150},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "draft"


def test_man_006_patch_event_publish_and_whitelist(client):
    ev = client.post("/api/manager/events", json={"title": "Avatar 3", "event_type": "movie"}).json()
    res = client.patch(
        f"/api/manager/events/{ev['id']}",
        json={"status": "published", "created_at": "1999-01-01"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "published"


def test_man_007_create_show_populates_fallback_show_seats(client, fake_db):
    ev = client.post(
        "/api/manager/events",
        json={"title": "Test Show", "event_type": "movie", "duration_minutes": 120, "status": "published"},
    ).json()
    v = client.post("/api/manager/venues", json={"name": "Arena", "city": "Rajkot"}).json()
    sc = client.post(f"/api/manager/venues/{v['id']}/screens", json={"name": "Hall A", "capacity": 30}).json()

    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    res = client.post(
        "/api/manager/shows",
        json={"event_id": ev["id"], "screen_id": sc["id"], "start_time": start, "base_price": 250.0},
    )
    assert res.status_code == 200
    show_id = res.json()["id"]
    show_seats = [ss for ss in fake_db.show_seats.values() if str(ss["show_id"]) == show_id]
    assert len(show_seats) == 30


def test_man_008_reject_end_time_before_start_time(client, fake_db):
    res = client.post(
        "/api/manager/shows",
        json={
            "event_id": fake_db.seed_event_id,
            "screen_id": fake_db.seed_screen_id,
            "start_time": "2026-11-20T18:00:00Z",
            "end_time": "2026-11-20T15:00:00Z",
            "base_price": 300.0,
        },
    )
    assert res.status_code == 400
    assert "strictly after start time" in res.json()["detail"].lower()


def test_man_009_reject_overlapping_show_conflict(client, fake_db):
    start = (fake_db.shows[fake_db.seed_show_id]["start_time"] + timedelta(minutes=30)).isoformat()
    res = client.post(
        "/api/manager/shows",
        json={
            "event_id": fake_db.seed_event_id,
            "screen_id": fake_db.seed_screen_id,
            "start_time": start,
            "base_price": 300.0,
        },
    )
    assert res.status_code == 409
    assert "Scheduling conflict" in res.json()["detail"]


def test_man_010_rbac_blocks_customer_and_unauthenticated(client, active_user):
    active_user["roles"] = ["customer"]
    res_cust = client.post("/api/manager/venues", json={"name": "X", "city": "Y"})
    assert res_cust.status_code == 403

    app_main.app.dependency_overrides.pop(get_current_user)
    res_unauth = client.post("/api/manager/venues", json={"name": "X", "city": "Y"})
    assert res_unauth.status_code in (401, 403)


def test_man_011_delete_unbooked_and_block_booked_show(client, fake_db, active_user):
    active_user["roles"] = ["admin"]
    start = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    created = client.post(
        "/api/manager/shows",
        json={
            "event_id": fake_db.seed_event_id,
            "screen_id": fake_db.seed_screen_id,
            "start_time": start,
            "base_price": 200.0,
        },
    ).json()

    assert client.delete(f"/api/manager/shows/{created['id']}").status_code == 200
    assert client.delete(f"/api/manager/shows/{fake_db.seed_show_id}").status_code == 409


@pytest.mark.xfail(reason="Known defect DEF-MAN-02: GET /api/browse/shows/{id} does not filter e.status='published'", strict=True)
def test_man_012_draft_event_show_blocked_from_direct_detail_url(client, fake_db):
    ev = client.post("/api/manager/events", json={"title": "Draft Film", "event_type": "movie"}).json()
    start = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    show = client.post(
        "/api/manager/shows",
        json={"event_id": ev["id"], "screen_id": fake_db.seed_screen_id, "start_time": start, "base_price": 200.0},
    ).json()

    res = client.get(f"/api/browse/shows/{show['id']}")
    assert res.status_code == 404

