from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncpg
from database import get_pool, close_pool
from firebase_admin_setup import init_firebase

from routers.auth import router as auth_router, admin_router
from routers.manager import router as manager_router
from routers.browse import router as browse_router
from routers.seats import router as seats_router
from routers.payments import router as payments_router
from routers.bookings import router as bookings_router
from routers.tickets import router as tickets_router

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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://ticketflow.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(manager_router)
app.include_router(browse_router)
app.include_router(seats_router)
app.include_router(payments_router)
app.include_router(bookings_router)
app.include_router(tickets_router)

@app.exception_handler(asyncpg.PostgresError)
async def postgres_error_handler(request: Request, exc: asyncpg.PostgresError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error while processing request."},
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
        headers={"Access-Control-Allow-Origin": "*"},
    )

@app.get("/")
def root():
    return {"status": "ok", "service": "TicketFlow API"}

@app.get("/health")
def health():
    return {"status": "healthy"}
