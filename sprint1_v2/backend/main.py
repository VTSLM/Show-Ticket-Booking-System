from __future__ import annotations

import logging
import re
import asyncpg
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from config import FRONTEND_URL
from database import get_pool, close_pool
from firebase_admin_setup import init_firebase

from routers.auth import router as auth_router, admin_router
from routers.manager import router as manager_router
from routers.browse import router as browse_router
from routers.seats import router as seats_router
from routers.payments import router as payments_router
from routers.bookings import router as bookings_router
from routers.tickets import router as tickets_router

logger = logging.getLogger("uvicorn.error")

_RAW_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ticketflow.vercel.app",
    FRONTEND_URL,
]
ALLOWED_ORIGINS = list(dict.fromkeys(o.rstrip("/") for o in _RAW_ORIGINS if o))
_LOCAL_ORIGIN_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")


def _cors_headers(request: Request) -> dict[str, str]:
    """Attach CORS headers even when an error bypasses route middleware."""
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin and (origin in ALLOWED_ORIGINS or _LOCAL_ORIGIN_RE.match(origin)):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_firebase()
    await get_pool()
    yield
    # Shutdown
    await close_pool()

app = FastAPI(
    title="TicketFlow API",
    description="Unified backend for the TicketFlow show booking system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
        headers=_cors_headers(request),
    )


@app.exception_handler(asyncpg.PostgresError)
async def postgres_exception_handler(request: Request, exc: asyncpg.PostgresError):
    logger.error("PostgreSQL error on %s %s: %s", request.method, request.url.path, exc)
    constraint = getattr(exc, "constraint_name", None)
    if isinstance(exc, asyncpg.CheckViolationError):
        detail = (
            "Show end time must be strictly after start time."
            if constraint == "shows_check"
            else f"Invalid field value (constraint '{constraint or 'check'}' violated)."
        )
        status_code = 400
    elif isinstance(exc, asyncpg.UniqueViolationError):
        detail = getattr(exc, "detail", None) or "A record with the same unique value already exists."
        status_code = 409
    elif isinstance(exc, asyncpg.ForeignKeyViolationError):
        if request.method == "DELETE":
            detail = "Cannot delete record because it is still referenced by existing records."
            status_code = 409
        else:
            detail = getattr(exc, "detail", None) or "Referenced record does not exist."
            status_code = 404
    elif isinstance(exc, asyncpg.DataError):
        detail = f"Invalid input data: {str(exc)}"
        status_code = 400
    else:
        detail = "Database error while processing request."
        status_code = 500

    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please check server logs."},
        headers=_cors_headers(request),
    )

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(manager_router)
app.include_router(browse_router)
app.include_router(seats_router)
app.include_router(payments_router)
app.include_router(bookings_router)
app.include_router(tickets_router)

@app.get("/")
def root():
    return {"status": "ok", "service": "TicketFlow API"}

@app.get("/health")
def health():
    return {"status": "healthy"}
