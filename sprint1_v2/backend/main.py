from contextlib import asynccontextmanager
from routers.venue_verification import router as venue_verification_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import get_pool, close_pool
from firebase_admin_setup import init_firebase
from routers.auth import router as auth_router, admin_router
from routers.manager import router as manager_router
from routers.browse import router as browse_router
from routers.seats import router as seats_router
from routers.payments import router as payments_router
from routers.bookings import router as bookings_router
from routers.cancellations import router as cancellations_router
from routers.tickets import router as tickets_router
from routers.support import router as support_router
from routers.support_admin import router as support_admin_router
from routers.venue_verification import router as venue_verification_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firebase()
    await get_pool()
    yield
    await close_pool()


app = FastAPI(
    title="TicketFlow API",
    description="Unified backend for the TicketFlow show booking system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://ticketflow.vercel.app"],
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
app.include_router(cancellations_router)
app.include_router(tickets_router)
app.include_router(support_router)
app.include_router(support_admin_router)
app.include_router(venue_verification_router)

@app.get("/")
def root():
    return {"status": "ok", "service": "TicketFlow API"}


@app.get("/health")
def health():
    return {"status": "healthy"}