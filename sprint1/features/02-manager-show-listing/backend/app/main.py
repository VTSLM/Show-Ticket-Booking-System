import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import check_db_health, close_db_pool, get_db_pool
from app.routers import events, screens, shows, venues

logger = logging.getLogger("uvicorn.error")
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: attempt to initialize DB pool if DATABASE_URL is present
    try:
        if settings.DATABASE_URL:
            await get_db_pool()
    except Exception as e:
        logger.warning(f"Could not connect to database on startup: {e}")
    yield
    # Shutdown: close pool
    await close_db_pool()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for Manager Event Creation and Show Listing (Sprint 1)",
    lifespan=lifespan,
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health & Diagnostics endpoint
@app.get("/api/manager/health", tags=["Health"])
async def health_check():
    db_status = await check_db_health()
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": db_status,
        "auth_bypass_enabled": settings.DEV_BYPASS_AUTH,
    }

# Register Feature Routers
app.include_router(events.router, prefix=settings.API_V1_STR)
app.include_router(venues.router, prefix=settings.API_V1_STR)
app.include_router(screens.router, prefix=settings.API_V1_STR)
app.include_router(shows.router, prefix=settings.API_V1_STR)

# Global safe error handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please check server logs."},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
