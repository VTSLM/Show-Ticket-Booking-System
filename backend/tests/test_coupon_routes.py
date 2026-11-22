"""The manager coupon routes must stay registered on the app (#197).

#197 reported "resource not found" when creating a coupon. The routes were fine; the request
reached a backend that did not have them yet. This guards against them going missing again
(router not included, prefix or path renamed).
"""
import pytest

import main


def registered() -> set[tuple[str, str]]:
    # the OpenAPI schema lists every route the app serves, including ones from included routers
    paths = main.app.openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/api/manager/coupons"),
        ("POST", "/api/manager/coupons"),
        ("PATCH", "/api/manager/coupons/{code}"),
    ],
)
def test_coupon_routes_are_registered(method, path):
    assert (method, path) in registered()


def test_frontend_and_backend_agree_on_the_coupon_paths():
    # frontend/lib/api.ts calls these exact paths
    with open("../frontend/lib/api.ts", encoding="utf-8") as f:
        api_ts = f.read()
    assert '"/api/manager/coupons"' in api_ts
    assert "`/api/manager/coupons/${encodeURIComponent(code)}`" in api_ts
