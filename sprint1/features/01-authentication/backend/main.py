"""
main.py — FastAPI application entry-point for the authentication service.

Run with:
    uvicorn main:app --reload --port 8001
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import close_pool, create_pool
from firebase_admin_setup import init_firebase
from router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_firebase()
    await create_pool()
    yield
    # Shutdown
    await close_pool()


app = FastAPI(
    title="Show Ticket Booking — Authentication Service",
    version="0.1.0",
    description="Handles user registration, login, role-based redirects, and admin approval workflow.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok"}
