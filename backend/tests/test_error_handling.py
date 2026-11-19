"""Unhandled errors return a JSON 500 that keeps CORS headers.

Without this, the browser hides the real failure behind a "CORS error".
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from error_handling import CatchUnhandledErrors

ORIGIN = "http://localhost:3000"


def _app():
    app = FastAPI()
    app.add_middleware(CatchUnhandledErrors)  # inner
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])  # outer

    @app.get("/boom")
    async def boom():
        raise RuntimeError("database exploded: secret details")

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    return app


def test_unhandled_error_returns_json_500_with_cors_headers():
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/boom", headers={"Origin": ORIGIN})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_error_details_are_not_sent_to_the_client():
    client = TestClient(_app(), raise_server_exceptions=False)
    r = client.get("/boom", headers={"Origin": ORIGIN})
    assert "secret details" not in r.text


def test_normal_requests_are_untouched():
    client = TestClient(_app())
    r = client.get("/ok", headers={"Origin": ORIGIN})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_main_app_puts_the_error_middleware_inside_cors():
    import main

    names = [m.cls.__name__ for m in main.app.user_middleware]
    # user_middleware is ordered outermost first
    assert names.index("CORSMiddleware") < names.index("CatchUnhandledErrors")
