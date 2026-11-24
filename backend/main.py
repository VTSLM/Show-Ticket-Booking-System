from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
import asyncio
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ORIGINS, IS_PRODUCTION, check_production_settings
from database import get_pool, close_pool
from error_handling import CatchUnhandledErrors
from firebase_admin_setup import init_firebase
from path_ids import validate_path_ids
from rate_limit import RateLimitMiddleware
from routers.auth import router as auth_router, admin_router
from routers.manager import router as manager_router
from routers.browse import router as browse_router
from routers.seats import router as seats_router
from routers.payments import router as payments_router
from routers.bookings import router as bookings_router
from routers.cancellations import router as cancellations_router
from routers.tickets import router as tickets_router
from routers.reviews import router as reviews_router
from routers.support import router as support_router
from routers.profile import router as profile_router
from routers.verification_documents import router as verification_documents_router
from routers.organizer_verification import router as organizer_verification_router
from routers.organizer_admin import router as organizer_admin_router
from routers.support_admin import router as support_admin_router
from routers.admin_users import router as admin_users_router
from routers.venue_verification import router as venue_verification_router
from routers.wishlist import router as wishlist_router
from routers.notifications import router as notifications_router
from routers.chat import router as chat_router
from routers.manager_analytics import router as manager_analytics_router
from routers.ticket_transfers import router as ticket_transfers_router
from services.ticket_transfer import expire_pending_transfers
from services.transfer_demo_payments import reconcile_pending
from services.transfer_notifier import deliver_pending


async def _cleanup_expired_locks():
    """Background task: release seat locks whose timer has expired and notify clients."""
    from routers.seats import manager
    while True:
        await asyncio.sleep(120)  # runs every 2 minutes
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """UPDATE show_seats
                       SET status='available', locked_by=NULL, locked_until=NULL, locked_price=NULL
                       WHERE status='locked' AND locked_until < NOW()
                       RETURNING id, show_id"""
                )
                if rows:
                    by_show: dict[str, list[str]] = {}
                    for r in rows:
                        by_show.setdefault(str(r["show_id"]), []).append(str(r["id"]))
                    for s_id, seat_ids in by_show.items():
                        await manager.broadcast(s_id, {"type": "release", "seat_ids": seat_ids}, conn=conn)
                    print(f"[seat-cleanup] Released {len(rows)} expired seat lock(s)")
                await expire_pending_transfers(conn)
                await reconcile_pending(conn)
                await deliver_pending(conn)
        except Exception as e:
            print(f"[seat-cleanup] error: {e}")


async def _listen_seat_events():
    """Background task: listen to PostgreSQL NOTIFY for cross-instance seat sync."""
    from routers.seats import manager, INSTANCE_ID
    import json
    while True:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                def on_notify(connection, pid, channel, payload):
                    try:
                        data = json.loads(payload)
                        if data.get("instance_id") != INSTANCE_ID:
                            asyncio.create_task(
                                manager.broadcast(
                                    data["show_id"],
                                    data["message"],
                                    from_remote=True
                                )
                            )
                    except Exception:
                        pass

                await conn.add_listener("seat_events", on_notify)
                try:
                    while True:
                        await asyncio.sleep(3600)
                finally:
                    await conn.remove_listener("seat_events", on_notify)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_production_settings()
    init_firebase()
    await get_pool()
    cleanup_task = asyncio.create_task(_cleanup_expired_locks())
    listen_task = asyncio.create_task(_listen_seat_events())
    yield
    cleanup_task.cancel()
    listen_task.cancel()
    await close_pool()


app = FastAPI(
    title="TicketFlow API",
    description="Unified backend for the TicketFlow show booking system",
    version="1.0.0",
    lifespan=lifespan,
    # Malformed ids in URLs -> 404 before any database query (#140)
    dependencies=[Depends(validate_path_ids)],
    # The interactive API docs are for development only.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Added before CORS so it sits inside it: error responses keep their CORS headers.
app.add_middleware(CatchUnhandledErrors)

# Rate limiting. Added BEFORE CORS on purpose: the last middleware added is the
# outermost, so CORS headers are also put on 429 responses and the browser can
# show the "Too many requests" message instead of a CORS error.
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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
app.include_router(reviews_router)
app.include_router(support_router)
app.include_router(profile_router)
app.include_router(verification_documents_router)
app.include_router(organizer_verification_router)
app.include_router(organizer_admin_router)
app.include_router(support_admin_router)
app.include_router(admin_users_router)
app.include_router(venue_verification_router)
app.include_router(wishlist_router)
app.include_router(notifications_router)
app.include_router(chat_router)
app.include_router(manager_analytics_router)
app.include_router(ticket_transfers_router)

@app.get("/")
def root():
    return {"status": "ok", "service": "TicketFlow API"}


@app.get("/health")
def health():
    return {"status": "healthy"}
