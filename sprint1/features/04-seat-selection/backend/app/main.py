from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers import seat_selection, dev_simulator
from app.schemas.errors import AppAPIException, ErrorCode
from app.services.auth import init_firebase_admin
from app.services.db import init_db_pool, close_db_pool
from app.services.logging_config import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: initialize bounded connection pool and auth."""
    logger.info(f"Starting Seat Allocation service in '{settings.ENV}' environment.")
    await init_db_pool()
    init_firebase_admin()
    yield
    logger.info("Shutting down Seat Allocation service.")
    await close_db_pool()


app = FastAPI(
    title="Seat Selection & Allocation API",
    description="Customer-side atomic seat selection, hold countdown, and release.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV == "local" else None,
    redoc_url=None
)

# CORS configuration strictly bound to ALLOWED_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["ETag"]
)

# Register core feature routers
app.include_router(seat_selection.router)

# Dev-only payment simulation route (never registered in staging or production)
if settings.ENV == "local" and settings.ENABLE_DEV_PAYMENT_SIMULATOR:
    app.include_router(dev_simulator.router)
    logger.info("Mounted local Dev Payment Simulator router at /api/dev/simulate-payment.")


# Centralized error handlers conforming strictly to {"error": {"code", "message", "details"}}
@app.exception_handler(AppAPIException)
async def app_api_exception_handler(request: Request, exc: AppAPIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code.value if hasattr(exc.error_code, "value") else str(exc.error_code),
                "message": exc.error_message,
                "details": exc.error_details
            }
        },
        headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Parse validation errors into clean messages without raw python internal details
    errors = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err.get("loc", []) if l != "body"])
        errors.append(f"{loc}: {err.get('msg')}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": "Validation failed for request parameters.",
                "details": errors
            }
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)

    code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.INTERNAL_ERROR
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code.value,
                "message": str(exc.detail) if exc.detail else "Request failed.",
                "details": None
            }
        },
        headers=exc.headers
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    # Log internal stack trace securely server-side; NEVER leak stack trace to client
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "An internal server error occurred. Please try again shortly.",
                "details": None
            }
        }
    )
