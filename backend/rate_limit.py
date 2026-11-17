"""
Rate limiting for the TicketFlow API (Sprint 3).

Why: without limits, one client can hammer the API — brute-force the register
endpoint, spam reviews / reports / support tickets, hold every seat of a show,
or flood the search endpoint and slow the site down for everyone.

How it works
  * A sliding-window counter per "bucket" (rule + client). A client may make
    `limit` requests in any `window` seconds; the next one gets HTTP 429 with
    a Retry-After header and a readable message (the frontend shows it as a toast).
  * Specific rules (below) protect sensitive endpoints. A global per-IP limit
    covers everything else, so nobody can flood the API.
  * Logged-in users are counted per user, not per IP, so many students on the
    same campus Wi-Fi do not block each other. Anonymous requests are counted per IP.
  * In-memory, no extra library and no extra service.

Settings (environment variables, all optional)
  RATE_LIMIT_ENABLED          "true" (default) / "false" to switch it off
  RATE_LIMIT_TRUST_PROXY      "true" when the API runs behind a proxy / load balancer
                              (Azure, Vercel, Nginx ...): the client IP is then read
                              from X-Forwarded-For. Keep "false" when the API is
                              reached directly, otherwise the header can be faked.
  RATE_LIMIT_GLOBAL_PER_MIN   requests per minute per IP for every endpoint (default 600)

Limit: counters live in one process. With several workers/servers each keeps its
own count; use a shared store such as Redis if the API is scaled out.
"""
import hashlib
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Optional, Tuple

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


@dataclass(frozen=True)
class Rule:
    name: str
    method: str          # "POST", "GET", ... or "*" for any
    pattern: "re.Pattern[str]"
    limit: int           # requests allowed ...
    window: int          # ... per this many seconds
    by: str = "user"     # "user" (token, falls back to IP) or "ip"


def _rule(name: str, method: str, path_regex: str, limit: int, window: int, by: str = "user") -> Rule:
    return Rule(name, method, re.compile(path_regex), limit, window, by)


MIN, TEN_MIN = 60, 600

# First matching rule wins. {id} parts are matched with [^/]+.
DEFAULT_RULES: List[Rule] = [
    # Accounts — anonymous, so counted per IP
    _rule("register", "POST", r"^/auth/register$", 10, TEN_MIN, "ip"),
    _rule("verify-token", "POST", r"^/auth/verify-token$", 30, MIN, "ip"),
    # Reviews
    _rule("review-create", "POST", r"^/api/reviews$", 10, TEN_MIN),
    _rule("review-edit", "PATCH", r"^/api/reviews/[^/]+$", 20, MIN),
    _rule("review-comment", "POST", r"^/api/reviews/[^/]+/comments$", 10, MIN),
    _rule("review-report", "POST", r"^/api/reviews/[^/]+/report$", 10, TEN_MIN),
    _rule("review-upvote", "POST", r"^/api/reviews/[^/]+/upvote$", 30, MIN),
    # Booking & payment
    _rule("booking-create", "POST", r"^/api/bookings$", 10, MIN),
    _rule("booking-cancel", "POST", r"^/api/bookings/[^/]+/cancel$", 5, MIN),
    _rule("payment-order", "POST", r"^/api/payments/orders$", 10, MIN),
    _rule("payment-verify", "POST", r"^/api/payments/orders/[^/]+/verify$", 20, MIN),
    _rule("seat-lock", "POST", r"^/api/seats/[^/]+/(lock|release|lock-zone|release-zone)$", 60, MIN),
    # Support, wishlist, profile, documents
    _rule("support-create", "POST", r"^/api/support/requests$", 5, TEN_MIN),
    _rule("support-message", "POST", r"^/api/support/requests/[^/]+/(messages|reopen)$", 20, MIN),
    _rule("wishlist-write", "*", r"^/api/wishlist/[^/]+$", 60, MIN),
    _rule("profile-photo", "POST", r"^/api/profile/photo$", 10, TEN_MIN),
    _rule("verification-upload", "POST", r"^/api/verification(/.*)?$", 20, TEN_MIN),
    # Search is the heaviest read (fuzzy matching)
    _rule("browse-search", "GET", r"^/api/browse/shows$", 180, MIN, "ip"),
]

EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}
MAX_WINDOW = TEN_MIN


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class RateLimiter:
    """Sliding-window log: remembers the time of each recent request per key."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = {}
        self._last_sweep = clock()

    def check(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        """Return (allowed, retry_after_seconds). Counts the request when allowed."""
        now = self._clock()
        self._sweep(now)
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(hits[0] + window - now) + 1)
            return False, retry_after
        hits.append(now)
        return True, 0

    def _sweep(self, now: float) -> None:
        """Forget clients that have been quiet, so memory does not grow forever."""
        if now - self._last_sweep < 60:
            return
        self._last_sweep = now
        stale = [k for k, d in self._hits.items() if not d or d[-1] <= now - MAX_WINDOW]
        for k in stale:
            del self._hits[k]


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        rules: Optional[List[Rule]] = None,
        global_per_min: Optional[int] = None,
        enabled: Optional[bool] = None,
        trust_proxy: Optional[bool] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.app = app
        self.rules = DEFAULT_RULES if rules is None else rules
        self.global_per_min = (
            global_per_min if global_per_min is not None
            else int(os.getenv("RATE_LIMIT_GLOBAL_PER_MIN", "600"))
        )
        self.enabled = _env_bool("RATE_LIMIT_ENABLED", True) if enabled is None else enabled
        self.trust_proxy = _env_bool("RATE_LIMIT_TRUST_PROXY", False) if trust_proxy is None else trust_proxy
        self.limiter = RateLimiter(clock)

    # ── who is calling? ──
    def _client_ip(self, scope: Scope, headers: Dict[bytes, bytes]) -> str:
        if self.trust_proxy:
            forwarded = headers.get(b"x-forwarded-for", b"").decode("latin-1")
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        client = scope.get("client")
        return client[0] if client else "unknown"

    @staticmethod
    def _user_key(headers: Dict[bytes, bytes]) -> Optional[str]:
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if auth.lower().startswith("bearer ") and len(auth) > 7:
            return "u:" + hashlib.sha256(auth[7:].strip().encode()).hexdigest()[:24]
        return None

    def _match(self, method: str, path: str) -> Optional[Rule]:
        for rule in self.rules:
            if rule.method in ("*", method) and rule.pattern.match(path):
                return rule
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        # CORS preflight and health checks are never limited
        if method == "OPTIONS" or path in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        ip = self._client_ip(scope, headers)

        # 1) the specific rule for this endpoint, if any
        rule = self._match(method, path)
        if rule is not None:
            who = ip
            if rule.by == "user":
                who = self._user_key(headers) or ip
            ok, retry = self.limiter.check(f"{rule.name}|{who}", rule.limit, rule.window)
            if not ok:
                await self._reject(send, retry, rule.limit, rule.window)
                return

        # 2) the global per-IP limit (also stops floods of fake tokens)
        ok, retry = self.limiter.check(f"global|{ip}", self.global_per_min, MIN)
        if not ok:
            await self._reject(send, retry, self.global_per_min, MIN)
            return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, retry_after: int, limit: int, window: int) -> None:
        response = JSONResponse(
            status_code=429,
            content={"detail": f"Too many requests. Please try again in {retry_after} seconds."},
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Window": str(window),
            },
        )
        await response({"type": "http"}, _noop_receive, send)


async def _noop_receive():  # response objects need a receive callable
    return {"type": "http.request", "body": b"", "more_body": False}
