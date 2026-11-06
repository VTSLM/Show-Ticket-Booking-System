import hashlib
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timezone, timedelta
import asyncpg
from app.config import settings
from app.schemas.errors import AppAPIException, ErrorCode
from app.schemas.seat_selection import (
    SeatMapResponse,
    ShowDetails,
    ShowSeatItem,
    MyHoldSummary,
    HoldCreateResponse,
    HoldDetailResponse,
    ReleaseResponse
)
from app.services.db import get_pool
from app.services.logging_config import logger


def generate_etag(show_id: UUID, show_status: str, seat_count: int, seat_hash: str, user_id: Optional[UUID]) -> str:
    """Computes a deterministic ETag for 304 Not Modified caching."""
    user_str = str(user_id) if user_id else "guest"
    raw = f"{show_id}:{show_status}:{seat_count}:{seat_hash}:{user_str}"
    return f'"{hashlib.sha256(raw.encode()).hexdigest()[:16]}"'


async def get_seat_map_data(show_id: UUID, current_user_id: Optional[UUID]) -> Tuple[SeatMapResponse, str]:
    """
    Fetches the seat map layout, show metadata, and caller's active hold.
    Normalizes expired locks to available.
    Never leaks other users' IDs.
    Falls back to in-memory demo data when no DB is configured (local dev only).
    Returns (SeatMapResponse, etag).
    """
    pool = get_pool()
    if pool is None:
        # Local dev: no DB configured → serve the demo seat map so the UI is fully exercisable
        if settings.ENV == "local":
            from app.services.demo_data import build_demo_seat_map
            logger.info(
                "No DB pool — serving in-memory demo seat map for local development. "
                "Set DATABASE_URL to use live data."
            )
            return build_demo_seat_map(
                current_user_id=str(current_user_id) if current_user_id else None,
            )
        raise AppAPIException(
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Database connection pool unavailable.",
        )


    now_utc = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        # 1. Fetch Show and Event metadata
        show_row = await conn.fetchrow(
            """
            SELECT
                s.id AS show_id,
                s.start_time,
                s.status AS show_status,
                e.title,
                e.language,
                e.genre,
                e.duration,
                e.poster_url,
                sc.name AS screen_name,
                v.name AS venue_name,
                v.city AS venue_city
            FROM shows s
            JOIN events e ON e.id = s.event_id
            JOIN screens sc ON sc.id = s.screen_id
            JOIN venues v ON v.id = sc.venue_id
            WHERE s.id = $1;
            """,
            show_id
        )

        if not show_row:
            raise AppAPIException(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"Show with ID '{show_id}' not found."
            )

        start_time = show_row["start_time"]
        show_status = show_row["show_status"]

        # Determine bookability
        bookable = True
        bookable_reason = None

        if show_status == "cancelled":
            bookable = False
            bookable_reason = "This show has been cancelled."
        elif show_status == "completed":
            bookable = False
            bookable_reason = "This show has concluded."
        elif start_time <= now_utc:
            bookable = False
            bookable_reason = "This show has already started."

        # 2. Check for caller's active pending hold on this show
        my_hold: Optional[MyHoldSummary] = None
        if current_user_id:
            hold_row = await conn.fetchrow(
                """
                SELECT id, booking_number, expires_at, total_amount
                FROM bookings
                WHERE show_id = $1
                  AND user_id = $2
                  AND status = 'pending'
                  AND expires_at > $3
                ORDER BY created_at DESC
                LIMIT 1;
                """,
                show_id, current_user_id, now_utc
            )
            if hold_row:
                seat_id_rows = await conn.fetch(
                    "SELECT show_seat_id FROM booking_seats WHERE booking_id = $1",
                    hold_row["id"]
                )
                my_hold = MyHoldSummary(
                    booking_id=str(hold_row["id"]),
                    booking_number=hold_row["booking_number"],
                    expires_at=hold_row["expires_at"].isoformat(),
                    show_seat_ids=[str(r["show_seat_id"]) for r in seat_id_rows],
                    total_amount=float(hold_row["total_amount"]),
                )

        # 3. Query show_seats joined directly with seats (as required by Section 3)
        seat_rows = await conn.fetch(
            """
            SELECT
                ss.id AS show_seat_id,
                s.row_label,
                s.seat_number,
                s.seat_type,
                ss.price,
                ss.status,
                ss.locked_until,
                ss.locked_by
            FROM show_seats ss
            JOIN seats s ON s.id = ss.seat_id
            WHERE ss.show_id = $1
            ORDER BY s.row_label ASC, s.seat_number ASC;
            """,
            show_id
        )

        seats: List[ShowSeatItem] = []
        hash_parts = []

        for row in seat_rows:
            raw_status = row["status"]
            locked_until = row["locked_until"]
            locked_by = row["locked_by"]
            is_mine = False
            effective_status = raw_status

            if raw_status == "locked":
                # Expired locks past locked_until count as available everywhere
                if locked_until is None or locked_until <= now_utc:
                    effective_status = "available"
                    is_mine = False
                else:
                    if current_user_id and locked_by == current_user_id:
                        is_mine = True
                        effective_status = "locked"
                    else:
                        is_mine = False
                        effective_status = "locked"
            elif raw_status == "available":
                is_mine = False
            elif raw_status == "booked":
                is_mine = False
            elif raw_status == "reserved":
                is_mine = False

            seats.append(
                ShowSeatItem(
                    show_seat_id=str(row["show_seat_id"]),
                    row_label=row["row_label"],
                    seat_number=row["seat_number"],
                    seat_type=row["seat_type"],
                    price=float(row["price"]),
                    status=effective_status,
                    is_mine=is_mine
                )
            )
            hash_parts.append(f"{row['show_seat_id']}:{effective_status}:{is_mine}")

        show_details = ShowDetails(
            id=str(show_row["show_id"]),
            title=show_row["title"],
            language=show_row["language"],
            genre=show_row["genre"],
            duration=show_row["duration"],
            poster_url=show_row["poster_url"],
            venue=show_row["venue_name"],
            city=show_row["venue_city"],
            screen=show_row["screen_name"],
            start_time=start_time.isoformat(),
            status=show_status
        )

        response_data = SeatMapResponse(
            server_time=now_utc.isoformat(),
            show=show_details,
            max_seats_per_booking=settings.MAX_SEATS_PER_BOOKING,
            bookable=bookable,
            bookable_reason=bookable_reason,
            my_hold=my_hold,
            seats=seats
        )

        seat_hash = hashlib.md5(";".join(hash_parts).encode()).hexdigest()
        etag = generate_etag(show_id, show_status, len(seats), seat_hash, current_user_id)

        return response_data, etag


async def create_seat_hold(
    show_id: UUID,
    user_id: UUID,
    show_seat_ids: List[UUID],
    idempotency_key: str
) -> HoldCreateResponse:
    """
    Executes atomic seat hold in ONE transaction on ONE connection:
    1. Validates preconditions (show exists, scheduled, future, seats valid & within limit).
    2. Replays matching pending booking on identical Idempotency-Key.
    3. Cancels user's previous pending booking for this show.
    4. Calls lock_show_seats (atomic all-or-nothing, sorted IDs, retry deadlocks up to 2 times).
    5. Calls create_pending_booking.
    6. Returns 201 response.
    """
    # 1. Validation before locking
    if not show_seat_ids:
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="At least one seat must be selected."
        )

    deduped_ids = list(dict.fromkeys(show_seat_ids))
    if len(deduped_ids) != len(show_seat_ids):
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Duplicate seat selections detected."
        )

    if len(deduped_ids) > settings.MAX_SEATS_PER_BOOKING:
        raise AppAPIException(
            status_code=400,
            code=ErrorCode.MAX_SEATS_EXCEEDED,
            message=f"Cannot select more than {settings.MAX_SEATS_PER_BOOKING} seats per booking."
        )

    pool = get_pool()
    if pool is None:
        raise AppAPIException(
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Database connection pool unavailable."
        )

    # Global sort to eliminate deadlock cycle
    sorted_seat_ids = sorted(deduped_ids)

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # 1. Verify show existence, status, and future start time
                    show = await conn.fetchrow(
                        "SELECT id, start_time, status FROM shows WHERE id = $1 FOR SHARE",
                        show_id
                    )
                    if not show:
                        raise AppAPIException(
                            status_code=404,
                            code=ErrorCode.NOT_FOUND,
                            message=f"Show with ID '{show_id}' does not exist."
                        )

                    now_utc = datetime.now(timezone.utc)
                    if show["status"] != "scheduled":
                        raise AppAPIException(
                            status_code=400,
                            code=ErrorCode.SHOW_NOT_BOOKABLE,
                            message=f"Cannot book seats: show is currently '{show['status']}'."
                        )
                    if show["start_time"] <= now_utc:
                        raise AppAPIException(
                            status_code=400,
                            code=ErrorCode.SHOW_NOT_BOOKABLE,
                            message="Cannot book seats: show has already commenced."
                        )

                    # 2. Verify all seat IDs belong to this show
                    valid_count = await conn.fetchval(
                        "SELECT count(*) FROM show_seats WHERE id = ANY($1) AND show_id = $2",
                        sorted_seat_ids, show_id
                    )
                    if valid_count != len(sorted_seat_ids):
                        raise AppAPIException(
                            status_code=400,
                            code=ErrorCode.VALIDATION_ERROR,
                            message="One or more selected seats do not belong to this show."
                        )

                    # 3. Idempotency Check: Replay exact same active pending booking if key matches
                    if idempotency_key:
                        existing_booking = await conn.fetchrow(
                            """
                            SELECT id, booking_number, total_amount, expires_at
                            FROM bookings
                            WHERE user_id = $1
                              AND idempotency_key = $2
                              AND show_id = $3
                              AND status = 'pending'
                              AND expires_at > $4;
                            """,
                            user_id, idempotency_key, show_id, now_utc
                        )
                        if existing_booking:
                            b_seats = await conn.fetch(
                                "SELECT show_seat_id FROM booking_seats WHERE booking_id = $1",
                                existing_booking["id"]
                            )
                            logger.info(
                                f"Idempotent replay: returning existing booking {existing_booking['id']} "
                                f"for key '{idempotency_key}'"
                            )
                            return HoldCreateResponse(
                                booking_id=str(existing_booking["id"]),
                                booking_number=existing_booking["booking_number"],
                                total_amount=float(existing_booking["total_amount"]),
                                show_seat_ids=[str(r["show_seat_id"]) for r in b_seats],
                                expires_at=existing_booking["expires_at"].isoformat(),
                                server_time=now_utc.isoformat()
                            )

                    # 4. Cancel user's previous pending booking for this show
                    prev_pending_bookings = await conn.fetch(
                        """
                        SELECT id FROM bookings
                        WHERE show_id = $1 AND user_id = $2 AND status = 'pending';
                        """,
                        show_id, user_id
                    )
                    for prev in prev_pending_bookings:
                        await conn.execute("SELECT cancel_pending_booking($1, $2)", prev["id"], user_id)
                        logger.info(f"Auto-cancelled earlier pending booking {prev['id']} for user {user_id}")

                    # 5. Lock seats using atomic stored procedure
                    lock_duration_seconds = settings.SEAT_LOCK_MINUTES * 60
                    lock_result = await conn.fetchrow(
                        "SELECT success, failed_seat_ids FROM lock_show_seats($1, $2, $3, $4)",
                        show_id, sorted_seat_ids, user_id, lock_duration_seconds
                    )

                    if not lock_result or not lock_result["success"]:
                        failed_ids = [str(f) for f in (lock_result["failed_seat_ids"] or [])]
                        logger.warning(f"Atomic hold rejected: seats {failed_ids} unavailable.")
                        raise AppAPIException(
                            status_code=409,
                            code=ErrorCode.SEATS_UNAVAILABLE,
                            message="One or more selected seats were just taken. Your other seats remain selected.",
                            details={"failed_seat_ids": failed_ids}
                        )

                    # 6. Calculate total amount
                    total_amount = await conn.fetchval(
                        "SELECT SUM(price) FROM show_seats WHERE id = ANY($1)",
                        sorted_seat_ids
                    )
                    expires_at = now_utc + timedelta(seconds=lock_duration_seconds)

                    # 7. Create pending booking via stored function
                    booking_row = await conn.fetchrow(
                        """
                        SELECT booking_id, booking_number, total_amount, expires_at, show_seat_ids
                        FROM create_pending_booking($1, $2, $3, $4, $5, $6);
                        """,
                        show_id, user_id, sorted_seat_ids, idempotency_key, total_amount, expires_at
                    )

                    logger.info(
                        f"Held {len(sorted_seat_ids)} seats in booking {booking_row['booking_id']} "
                        f"for user {user_id}"
                    )

                    return HoldCreateResponse(
                        booking_id=str(booking_row["booking_id"]),
                        booking_number=booking_row["booking_number"],
                        total_amount=float(booking_row["total_amount"]),
                        show_seat_ids=[str(s) for s in sorted_seat_ids],
                        expires_at=booking_row["expires_at"].isoformat(),
                        server_time=now_utc.isoformat()
                    )

        except asyncpg.DeadlockDetectedError:
            if attempt < max_retries:
                logger.warning(f"Deadlock detected during lock_show_seats. Retrying attempt {attempt + 1}...")
                continue
            logger.error("Deadlock persisted after 2 retries.")
            raise AppAPIException(
                status_code=503,
                code=ErrorCode.SERVICE_UNAVAILABLE,
                message="Seat allocation service is experiencing high contention. Please try again."
            )
        except AppAPIException:
            raise
        except Exception as exc:
            logger.error(f"Unexpected error in create_seat_hold: {exc}", exc_info=True)
            raise AppAPIException(
                status_code=500,
                code=ErrorCode.INTERNAL_ERROR,
                message="An unexpected server error occurred while holding seats."
            )


async def release_user_hold(booking_id: UUID, user_id: UUID) -> ReleaseResponse:
    """
    Releases a user's held booking (owner-only, idempotent).
    Returns 404 if booking belongs to another user or does not exist.
    """
    pool = get_pool()
    if pool is None:
        raise AppAPIException(
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Database connection pool unavailable."
        )

    async with pool.acquire() as conn:
        booking = await conn.fetchrow(
            "SELECT id, user_id, status FROM bookings WHERE id = $1",
            booking_id
        )
        if not booking or booking["user_id"] != user_id:
            # Another user's booking returns 404 to avoid leaking existence
            raise AppAPIException(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"Hold booking with ID '{booking_id}' not found."
            )

        if booking["status"] == "pending":
            await conn.execute("SELECT cancel_pending_booking($1, $2)", booking_id, user_id)
            logger.info(f"Released pending hold {booking_id} for user {user_id}")

        return ReleaseResponse(
            success=True,
            message="Seat hold released successfully.",
            booking_id=str(booking_id)
        )


async def get_hold_details(booking_id: UUID, user_id: UUID) -> HoldDetailResponse:
    """
    Fetches hold state for checkout transition (owner-only).
    Another user's booking returns 404.
    """
    pool = get_pool()
    if pool is None:
        raise AppAPIException(
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Database connection pool unavailable."
        )

    now_utc = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        booking = await conn.fetchrow(
            """
            SELECT id, booking_number, show_id, user_id, status, total_amount, expires_at
            FROM bookings
            WHERE id = $1;
            """,
            booking_id
        )
        if not booking or booking["user_id"] != user_id:
            raise AppAPIException(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"Hold booking with ID '{booking_id}' not found."
            )

        if booking["status"] == "pending" and booking["expires_at"] and booking["expires_at"] <= now_utc:
            # Mark expired
            await conn.execute("UPDATE bookings SET status = 'expired' WHERE id = $1", booking_id)
            raise AppAPIException(
                status_code=410,
                code=ErrorCode.HOLD_EXPIRED,
                message="Your seat hold has expired. The seats have been released."
            )

        seat_rows = await conn.fetch(
            "SELECT show_seat_id FROM booking_seats WHERE booking_id = $1",
            booking_id
        )

        return HoldDetailResponse(
            booking_id=str(booking["id"]),
            booking_number=booking["booking_number"],
            show_id=str(booking["show_id"]),
            show_seat_ids=[str(r["show_seat_id"]) for r in seat_rows],
            total_amount=float(booking["total_amount"]),
            expires_at=booking["expires_at"].isoformat() if booking["expires_at"] else "",
            status=booking["status"],
            server_time=now_utc.isoformat()
        )


async def simulate_booking_payment(booking_id: UUID, user_id: UUID) -> bool:
    """
    DEV ONLY: Calls confirm_booking_payment to simulate successful payment gateway callback.
    Must never be called in staging or production.
    """
    if settings.ENV != "local" or not settings.ENABLE_DEV_PAYMENT_SIMULATOR:
        raise AppAPIException(
            status_code=403,
            code=ErrorCode.UNAUTHENTICATED,
            message="Payment simulator is disabled in this environment."
        )

    pool = get_pool()
    if pool is None:
        raise AppAPIException(
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Database connection pool unavailable."
        )

    async with pool.acquire() as conn:
        success = await conn.fetchval(
            "SELECT confirm_booking_payment($1, $2)",
            booking_id, user_id
        )
        return bool(success)
