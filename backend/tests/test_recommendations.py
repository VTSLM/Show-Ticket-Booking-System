"""Personalized recommendations and trending (#218). The database and the model are mocked."""
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from routers import recommendations as router
from services import recommendations as rec

NOW = datetime.now(timezone.utc)

E_THRILLER = str(uuid.uuid4())
E_COMEDY = str(uuid.uuid4())
E_CONCERT = str(uuid.uuid4())
E_BOOKED = str(uuid.uuid4())


def show(event_id, title, genre, event_type="movie", city="Ahmedabad", days=2,
         lat=23.03, lng=72.58, artists=(), price=200):
    return {
        "show_id": uuid.uuid4(), "start_time": NOW + timedelta(days=days), "dynamic_pricing": False,
        "event_id": uuid.UUID(event_id), "title": title, "event_type": event_type,
        "language": "Hindi", "genre": genre, "poster_url": None,
        "artists": json.dumps([{"name": a, "role": "Lead"} for a in artists]), "cast_crew": "[]",
        "venue_id": uuid.uuid4(), "venue_name": "Hall", "city": city,
        "latitude": lat, "longitude": lng, "base_price": price,
        "available_seats": 50, "sold_seats": 10, "total_seats": 60,
    }


SHOWS = [
    show(E_THRILLER, "Night Chase", "Crime, Thriller", artists=["Asha Rao"]),
    show(E_COMEDY, "Laugh Riot", "Comedy", days=1),
    # a concert far away is still listed when a location is sent (same rule as Browse)
    show(E_CONCERT, "Rock Night", "Rock", event_type="concert", city="Mumbai",
         lat=19.07, lng=72.87, artists=["The Band"]),
    show(E_BOOKED, "Dark Alley", "Thriller", days=3),
]


class FakeConn:
    def __init__(self, shows=SHOWS, bookings=None, prefs=None, taste=(), execute_status="INSERT 0 1"):
        self.shows = shows
        self.bookings = bookings or {}
        self.prefs = prefs
        self.taste = list(taste)
        self.execute_status = execute_status
        self.executed = []

    async def fetch(self, query, *args):
        if "FROM venues" in query:
            return [{"id": s["venue_id"], "city": s["city"], "latitude": s["latitude"],
                     "longitude": s["longitude"]} for s in self.shows]
        if "WITH upcoming" in query:
            near = args[0]
            return [dict(s) for s in self.shows
                    if near is None or s["event_type"] == "concert" or str(s["venue_id"]) in near]
        if "AVG(r.rating)" in query:
            return []
        if "COUNT(DISTINCT b.id)" in query:
            return [{"event_id": uuid.UUID(k), "bookings": v} for k, v in self.bookings.items()]
        if "UNION ALL" in query:
            return self.taste
        raise AssertionError(f"unexpected query: {query[:60]}")

    async def fetchrow(self, query, *args):
        if "user_preferences" in query:
            return self.prefs
        raise AssertionError(f"unexpected query: {query[:60]}")

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return self.execute_status


def taste_row(event_id, title, genre, source, event_type="movie", artists=(), times=1):
    return {"id": uuid.UUID(event_id), "title": title, "genre": genre, "event_type": event_type,
            "artists": json.dumps([{"name": a} for a in artists]), "cast_crew": "[]",
            "source": source, "times": times}


USER = {"id": "user-1", "status": "active"}


@pytest.fixture(autouse=True)
def _clear_cache():
    rec._reasons_cache.clear()
    yield
    rec._reasons_cache.clear()


# ── helpers ──────────────────────────────────────────────────────────────────

def test_words_and_artist_names():
    assert rec.words("Sci-Fi / Thriller") == {"sci", "fi", "thriller"}
    assert rec.artist_names('[{"name": " A  R Rahman "}, {"role": "x"}, "Zakir"]') == ["A R Rahman", "Zakir"]
    assert rec.artist_names("not json") == []


def test_clean_list_trims_dedupes_and_caps():
    values = ["  Thriller ", "thriller", "", 5, "x" * 80] + [f"g{i}" for i in range(20)]
    out = rec.clean_list(values)
    assert out[0] == "Thriller"
    assert len(out[1]) == rec.MAX_PREFERENCE_LENGTH
    assert len(out) == rec.MAX_PREFERENCE_ITEMS


def test_parse_reasons_keeps_known_ids_only():
    text = 'Sure! {"reasons": {"a": "  Great  pick ", "zzz": "ignored", "b": 4}} done'
    assert rec._parse_reasons(text, {"a", "b"}) == {"a": "Great pick"}
    assert rec._parse_reasons("no json here", {"a"}) == {}


# ── candidates and trending ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_location_keeps_nearby_shows_and_all_concerts():
    far_movie = show(str(uuid.uuid4()), "Far Movie", "Drama", city="Kolkata", lat=22.57, lng=88.36)
    conn = FakeConn(shows=SHOWS + [far_movie])
    events = await rec.load_candidates(conn, lat=23.02, lng=72.57)
    titles = {e["title"] for e in events}
    assert "Rock Night" in titles          # concert in Mumbai, outside 100 km
    assert "Far Movie" not in titles
    assert "Night Chase" in titles


@pytest.mark.asyncio
async def test_trending_orders_by_recent_bookings():
    conn = FakeConn(bookings={E_COMEDY: 9, E_THRILLER: 2})
    events = await rec.load_candidates(conn)
    top = await rec.trending(conn, events)
    assert [t["title"] for t in top[:2]] == ["Laugh Riot", "Night Chase"]
    assert top[0]["recent_bookings"] == 9


# ── scoring ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_picks_follow_bookings_and_skip_booked_events():
    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked")])
    taste = await rec.load_taste(conn, "user-1")
    picks = rec.personal_picks(await rec.load_candidates(conn), taste)
    titles = [p["title"] for p in picks]
    assert titles == ["Night Chase"]               # comedy and concert don't match, booked one is skipped
    assert picks[0]["match"][0] == "Because you booked Dark Alley"


@pytest.mark.asyncio
async def test_preferences_alone_give_picks_with_labels():
    prefs = {"genres": ["Rock"], "artists": ["Asha Rao"], "cities": ["Mumbai"], "updated_at": NOW}
    conn = FakeConn(prefs=prefs)
    taste = await rec.load_taste(conn, "user-1")
    picks = rec.personal_picks(await rec.load_candidates(conn), taste)
    by_title = {p["title"]: p for p in picks}
    assert set(by_title) == {"Rock Night", "Night Chase"}
    assert by_title["Rock Night"]["match"] == ["You like Rock", "In Mumbai"]
    assert by_title["Night Chase"]["match"] == ["Features Asha Rao"]
    assert "preferences" in taste["sources"]


@pytest.mark.asyncio
async def test_rating_alone_is_not_a_match():
    taste = await rec.load_taste(FakeConn(), "user-1")
    event = {"event_id": "x", "genre": "Comedy", "event_type": "movie", "artists": [],
             "cities": {"Pune"}, "avg_rating": 9.5}
    assert rec.score_event(event, taste) == (0.0, [])
    assert not rec.has_taste(taste)


# ── the full response ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_guest_gets_trending_only():
    result = await rec.build(FakeConn(bookings={E_COMEDY: 3}), None)
    assert result["personalized"] is False
    assert result["fallback"] == "guest"
    assert result["recommended"] == []
    assert result["trending"][0]["title"] == "Laugh Riot"


@pytest.mark.asyncio
async def test_new_user_without_history_falls_back_to_trending():
    result = await rec.build(FakeConn(), USER)
    assert result["fallback"] == "no_history"
    assert result["recommended"] == [] and result["trending"]


@pytest.mark.asyncio
async def test_model_reasons_are_added_and_cached(monkeypatch):
    calls = []

    async def fake_model(picks, taste):
        calls.append([p["event_id"] for p in picks])
        return {E_THRILLER: "Another tense crime thriller, like the one you booked."}

    monkeypatch.setattr(rec, "_ask_model", fake_model)
    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked")])

    first = await rec.build(conn, USER)
    second = await rec.build(conn, USER)

    assert first["personalized"] and first["ai_reasons"] and first["fallback"] is None
    assert first["recommended"][0]["reason"].startswith("Another tense")
    assert first["based_on"] == ["your bookings"]
    assert second["recommended"][0]["reason"] == first["recommended"][0]["reason"]
    assert len(calls) == 1                       # second request came from the cache


@pytest.mark.asyncio
async def test_slow_model_returns_picks_without_reasons(monkeypatch):
    async def slow_model(picks, taste):
        await asyncio.sleep(5)
        return {}

    monkeypatch.setattr(rec, "_ask_model", slow_model)
    monkeypatch.setenv("RECOMMENDATIONS_TIMEOUT_SECONDS", "0.5")
    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked")])

    started = asyncio.get_event_loop().time()
    result = await rec.build(conn, USER)
    assert asyncio.get_event_loop().time() - started < 2
    assert result["fallback"] == "ai_timeout"
    assert result["ai_reasons"] is False
    assert result["recommended"][0]["title"] == "Night Chase"
    assert result["recommended"][0]["reason"] is None
    assert result["trending"]                    # NFR5: trending is shown with the picks


@pytest.mark.asyncio
async def test_model_errors_do_not_break_recommendations(monkeypatch):
    async def broken(picks, taste):
        raise RuntimeError("OPENAI_API_KEY is not configured")

    monkeypatch.setattr(rec, "_ask_model", broken)
    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked")])
    result = await rec.build(conn, USER)
    assert result["fallback"] == "ai_unavailable"
    assert result["recommended"]


@pytest.mark.asyncio
async def test_ai_can_be_switched_off(monkeypatch):
    async def must_not_run(picks, taste):
        raise AssertionError("model called")

    monkeypatch.setattr(rec, "_ask_model", must_not_run)
    monkeypatch.setenv("RECOMMENDATIONS_AI", "false")
    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked")])
    result = await rec.build(conn, USER)
    assert result["fallback"] == "ai_off" and result["recommended"]


# ── router ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_view_of_bad_or_unpublished_event_is_404():
    with pytest.raises(HTTPException) as bad:
        await router.record_event_view("not-a-uuid", current_user=USER, conn=FakeConn())
    assert bad.value.status_code == 404

    conn = FakeConn(execute_status="INSERT 0 0")
    with pytest.raises(HTTPException) as missing:
        await router.record_event_view(E_COMEDY, current_user=USER, conn=conn)
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_view_is_recorded_for_the_logged_in_user():
    conn = FakeConn()
    assert await router.record_event_view(E_COMEDY, current_user=USER, conn=conn) == {"recorded": True}
    query, args = conn.executed[0]
    assert "ON CONFLICT (user_id, event_id)" in query
    assert args == ("user-1", E_COMEDY)


@pytest.mark.asyncio
async def test_saving_preferences_cleans_the_lists():
    conn = FakeConn(prefs={"genres": ["Thriller"], "artists": [], "cities": [], "updated_at": NOW})
    body = router.PreferencesBody(genres=[" Thriller ", "thriller"], artists=[], cities=[])
    await router.update_my_preferences(body, current_user=USER, conn=conn)
    _, args = conn.executed[0]
    assert args[1] == ["Thriller"]


def test_preferences_body_limits_the_list_size():
    with pytest.raises(ValueError):
        router.PreferencesBody(genres=[f"g{i}" for i in range(rec.MAX_PREFERENCE_ITEMS + 1)])


@pytest.mark.asyncio
async def test_half_a_location_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await router.get_recommendations(lat=23.0, lng=None, radius_km=100, auth=None, conn=FakeConn())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_saved_or_viewed_events_are_not_picked_again():
    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked"),
                           taste_row(E_THRILLER, "Night Chase", "Crime, Thriller", "viewed")])
    taste = await rec.load_taste(conn, "user-1")
    assert rec.personal_picks(await rec.load_candidates(conn), taste) == []


@pytest.mark.asyncio
async def test_card_shows_the_preferred_city():
    two_cities = [show(E_COMEDY, "Laugh Riot", "Comedy", city="Pune", days=1),
                  show(E_COMEDY, "Laugh Riot", "Comedy", city="Surat", days=2)]
    prefs = {"genres": ["Comedy"], "artists": [], "cities": ["Surat"], "updated_at": NOW}
    conn = FakeConn(shows=two_cities, prefs=prefs)
    taste = await rec.load_taste(conn, "user-1")
    [pick] = rec.personal_picks(await rec.load_candidates(conn), taste)
    assert pick["city"] == "Surat"
    assert rec.card(pick)["match"] == ["You like Comedy", "In Surat"]


@pytest.mark.asyncio
async def test_model_gets_only_the_listed_facts(monkeypatch):
    from types import SimpleNamespace
    from services import chatbot

    sent = {}

    async def create(**kwargs):
        sent.update(kwargs)
        text = json.dumps({"reasons": {E_THRILLER: "A crime thriller with Asha Rao."}})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(chatbot, "_get_client", lambda: client)
    monkeypatch.setenv("CHAT_PROVIDER", "openai")
    monkeypatch.setenv("CHAT_MODEL", "test-model")

    conn = FakeConn(taste=[taste_row(E_BOOKED, "Dark Alley", "Thriller", "booked")])
    result = await rec.build(conn, USER)

    assert result["recommended"][0]["reason"] == "A crime thriller with Asha Rao."
    assert sent["model"] == "test-model"
    payload = json.loads(sent["messages"][1]["content"])
    assert payload["events"][0]["title"] == "Night Chase"
    assert payload["user"]["recent_events"] == [{"title": "Dark Alley", "how": "booked"}]
    assert "user-1" not in sent["messages"][1]["content"]     # no ids or personal details
