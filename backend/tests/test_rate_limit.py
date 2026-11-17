import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from rate_limit import Rule, RateLimiter, RateLimitMiddleware


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_app(rules, clock=None, **kwargs):
    app = FastAPI()

    @app.post("/api/things")
    def things():
        return {"ok": True}

    @app.get("/api/other")
    def other():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    app.add_middleware(
        RateLimitMiddleware, rules=rules, clock=clock or FakeClock(), enabled=True, **kwargs
    )
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"])
    return app


THINGS = Rule("things", "POST", re.compile(r"^/api/things$"), 3, 60, "user")


def test_limiter_blocks_after_limit_and_recovers():
    clock = FakeClock()
    limiter = RateLimiter(clock)
    assert [limiter.check("k", 2, 60)[0] for _ in range(2)] == [True, True]
    allowed, retry = limiter.check("k", 2, 60)
    assert allowed is False and retry >= 1
    clock.now += 61
    assert limiter.check("k", 2, 60)[0] is True


def test_limiter_keys_are_independent():
    limiter = RateLimiter(FakeClock())
    assert limiter.check("a", 1, 60)[0] is True
    assert limiter.check("a", 1, 60)[0] is False
    assert limiter.check("b", 1, 60)[0] is True


def test_endpoint_returns_429_with_message_and_retry_after():
    client = TestClient(make_app([THINGS]))
    for _ in range(3):
        assert client.post("/api/things").status_code == 200
    res = client.post("/api/things")
    assert res.status_code == 429
    assert "Too many requests" in res.json()["detail"]
    assert int(res.headers["Retry-After"]) >= 1


def test_429_still_carries_cors_headers():
    client = TestClient(make_app([THINGS]))
    for _ in range(3):
        client.post("/api/things", headers={"Origin": "http://localhost:3000"})
    res = client.post("/api/things", headers={"Origin": "http://localhost:3000"})
    assert res.status_code == 429
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_window_reopens_after_time_passes():
    clock = FakeClock()
    client = TestClient(make_app([THINGS], clock))
    for _ in range(3):
        client.post("/api/things")
    assert client.post("/api/things").status_code == 429
    clock.now += 61
    assert client.post("/api/things").status_code == 200


def test_logged_in_users_are_counted_separately():
    client = TestClient(make_app([THINGS]))
    for _ in range(3):
        assert client.post("/api/things", headers={"Authorization": "Bearer token-a"}).status_code == 200
    assert client.post("/api/things", headers={"Authorization": "Bearer token-a"}).status_code == 429
    # another user on the same IP is not affected
    assert client.post("/api/things", headers={"Authorization": "Bearer token-b"}).status_code == 200


def test_ip_rule_is_shared_by_everyone_on_that_ip():
    rule = Rule("things", "POST", re.compile(r"^/api/things$"), 2, 60, "ip")
    client = TestClient(make_app([rule]))
    assert client.post("/api/things", headers={"Authorization": "Bearer a"}).status_code == 200
    assert client.post("/api/things", headers={"Authorization": "Bearer b"}).status_code == 200
    assert client.post("/api/things", headers={"Authorization": "Bearer c"}).status_code == 429


def test_global_limit_applies_to_unmatched_routes():
    client = TestClient(make_app([], global_per_min=2))
    assert client.get("/api/other").status_code == 200
    assert client.get("/api/other").status_code == 200
    assert client.get("/api/other").status_code == 429


def test_health_and_preflight_are_never_limited():
    client = TestClient(make_app([], global_per_min=1))
    for _ in range(5):
        assert client.get("/health").status_code == 200
    for _ in range(5):
        res = client.options(
            "/api/things",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
        )
        assert res.status_code == 200


def test_x_forwarded_for_only_trusted_when_enabled():
    rule = Rule("things", "POST", re.compile(r"^/api/things$"), 1, 60, "ip")
    # not trusted: a faked header cannot create new buckets
    client = TestClient(make_app([rule], trust_proxy=False))
    assert client.post("/api/things", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.post("/api/things", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429
    # trusted: each forwarded client has its own bucket
    client = TestClient(make_app([rule], trust_proxy=True))
    assert client.post("/api/things", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.post("/api/things", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    assert client.post("/api/things", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429


def test_disabled_switch_lets_everything_through():
    app = FastAPI()

    @app.post("/api/things")
    def things():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, rules=[THINGS], enabled=False)
    client = TestClient(app)
    for _ in range(10):
        assert client.post("/api/things").status_code == 200
