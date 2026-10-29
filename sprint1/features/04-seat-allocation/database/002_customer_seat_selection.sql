-- ==============================================================================
-- Schema: Show Booking System - Feature 04: Seat Selection & Allocation
-- Target: PostgreSQL 14+ / Supabase
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid VARCHAR(128) UNIQUE NOT NULL,
    email VARCHAR(255),
    name VARCHAR(255),
    is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Venues Table
CREATE TABLE IF NOT EXISTS venues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Screens Table
CREATE TABLE IF NOT EXISTS screens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Seats Table (Physical auditorium seats)
CREATE TABLE IF NOT EXISTS seats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    screen_id UUID NOT NULL REFERENCES screens(id) ON DELETE CASCADE,
    row_label VARCHAR(10) NOT NULL,
    seat_number INT NOT NULL,
    seat_type VARCHAR(20) NOT NULL CHECK (seat_type IN ('standard', 'premium', 'accessible')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_screen_row_number UNIQUE (screen_id, row_label, seat_number)
);

-- 5. Events Table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    language VARCHAR(50) NOT NULL,
    genre VARCHAR(50) NOT NULL,
    duration INT NOT NULL, -- duration in minutes
    poster_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. Shows Table
CREATE TABLE IF NOT EXISTS shows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    screen_id UUID NOT NULL REFERENCES screens(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'cancelled', 'completed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Show Seats Table (Dynamic state per show instance)
-- "reserved" = administrative hold, not sellable.
-- "locked" = held by a user; if NOW() > locked_until, it is normalized to available.
CREATE TABLE IF NOT EXISTS show_seats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    show_id UUID NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    seat_id UUID NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'locked', 'booked', 'reserved')),
    locked_until TIMESTAMPTZ,
    locked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_show_seat UNIQUE (show_id, seat_id)
);

CREATE INDEX IF NOT EXISTS idx_show_seats_show_id ON show_seats(show_id);
CREATE INDEX IF NOT EXISTS idx_show_seats_status ON show_seats(status);
CREATE INDEX IF NOT EXISTS idx_show_seats_locked_by ON show_seats(locked_by);

-- 8. Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_number VARCHAR(32) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    show_id UUID NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'cancelled', 'expired')),
    total_amount NUMERIC(10, 2) NOT NULL CHECK (total_amount >= 0),
    idempotency_key VARCHAR(128),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bookings_user_show ON bookings(user_id, show_id);
CREATE INDEX IF NOT EXISTS idx_bookings_idempotency ON bookings(user_id, idempotency_key);

-- 9. Booking Seats Junction Table
CREATE TABLE IF NOT EXISTS booking_seats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    show_seat_id UUID NOT NULL REFERENCES show_seats(id) ON DELETE CASCADE,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    CONSTRAINT uq_booking_show_seat UNIQUE (booking_id, show_seat_id)
);

-- ==============================================================================
-- STORED FUNCTIONS (Fixed Contract - Called by Backend)
-- ==============================================================================

-- 1. Atomic all-or-nothing seat locking function.
-- Sorts seat IDs before locking to guarantee lock order and avoid cross-transaction deadlocks.
-- Verifies that every single requested seat is available (or locked by this user, or has an expired lock).
-- If any seat fails, returns success = false and the list of failed seat IDs; rolls back all changes.
CREATE OR REPLACE FUNCTION lock_show_seats(
    p_show_id UUID,
    p_show_seat_ids UUID[],
    p_user_id UUID,
    p_lock_duration_seconds INT
)
RETURNS TABLE (
    success BOOLEAN,
    failed_seat_ids UUID[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_now TIMESTAMPTZ := clock_timestamp();
    v_locked_until TIMESTAMPTZ := v_now + (p_lock_duration_seconds || ' seconds')::INTERVAL;
    v_failed_ids UUID[];
    v_requested_count INT;
    v_available_count INT;
BEGIN
    v_requested_count := array_length(p_show_seat_ids, 1);
    IF v_requested_count IS NULL OR v_requested_count = 0 THEN
        RETURN QUERY SELECT FALSE, ARRAY[]::UUID[];
        RETURN;
    END IF;

    -- Row-level locking ordered by ID to eliminate lock inversion deadlocks
    PERFORM id
    FROM show_seats
    WHERE id = ANY(p_show_seat_ids) AND show_id = p_show_id
    ORDER BY id
    FOR UPDATE;

    -- Find all seat IDs that are NOT available:
    -- A seat is unavailable if:
    -- 1. Status is 'booked'
    -- 2. Status is 'reserved'
    -- 3. Status is 'locked', lock has NOT expired (locked_until > v_now), and NOT held by current user
    -- 4. The seat ID does not belong to this show or does not exist
    SELECT ARRAY_AGG(req_id)
    INTO v_failed_ids
    FROM unnest(p_show_seat_ids) AS req_id
    LEFT JOIN show_seats ss ON ss.id = req_id AND ss.show_id = p_show_id
    WHERE ss.id IS NULL
       OR ss.status = 'booked'
       OR ss.status = 'reserved'
       OR (ss.status = 'locked' AND ss.locked_until > v_now AND (ss.locked_by IS NULL OR ss.locked_by <> p_user_id));

    IF v_failed_ids IS NOT NULL AND array_length(v_failed_ids, 1) > 0 THEN
        -- All-or-nothing: conflict detected, zero seats locked
        RETURN QUERY SELECT FALSE, v_failed_ids;
        RETURN;
    END IF;

    -- All requested seats are available: atomically apply the lock
    UPDATE show_seats
    SET status = 'locked',
        locked_by = p_user_id,
        locked_until = v_locked_until,
        updated_at = v_now
    WHERE id = ANY(p_show_seat_ids) AND show_id = p_show_id;

    RETURN QUERY SELECT TRUE, ARRAY[]::UUID[];
END;
$$;

-- 2. Create pending booking record and associate show seats
CREATE OR REPLACE FUNCTION create_pending_booking(
    p_show_id UUID,
    p_user_id UUID,
    p_show_seat_ids UUID[],
    p_idempotency_key TEXT,
    p_total_amount NUMERIC,
    p_expires_at TIMESTAMPTZ
)
RETURNS TABLE (
    booking_id UUID,
    booking_number VARCHAR(32),
    total_amount NUMERIC,
    expires_at TIMESTAMPTZ,
    show_seat_ids UUID[]
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_booking_id UUID;
    v_booking_number VARCHAR(32);
    v_seat_id UUID;
    v_seat_price NUMERIC(10, 2);
BEGIN
    -- Generate human-friendly booking number: BKG-XXXX-XXXX
    v_booking_number := 'BKG-' || upper(substr(md5(random()::text || clock_timestamp()::text), 1, 8));

    INSERT INTO bookings (
        booking_number,
        user_id,
        show_id,
        status,
        total_amount,
        idempotency_key,
        expires_at
    )
    VALUES (
        v_booking_number,
        p_user_id,
        p_show_id,
        'pending',
        p_total_amount,
        p_idempotency_key,
        p_expires_at
    )
    RETURNING id INTO v_booking_id;

    -- Insert booking_seats snapshot with current prices
    FOREACH v_seat_id IN ARRAY p_show_seat_ids LOOP
        SELECT price INTO v_seat_price FROM show_seats WHERE id = v_seat_id;
        INSERT INTO booking_seats (booking_id, show_seat_id, price)
        VALUES (v_booking_id, v_seat_id, COALESCE(v_seat_price, 0));
    END LOOP;

    RETURN QUERY SELECT
        v_booking_id,
        v_booking_number,
        p_total_amount,
        p_expires_at,
        p_show_seat_ids;
END;
$$;

-- 3. Cancel a pending booking and release its held seats
CREATE OR REPLACE FUNCTION cancel_pending_booking(
    p_booking_id UUID,
    p_user_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_booking_user_id UUID;
    v_status VARCHAR(20);
    v_seat_ids UUID[];
BEGIN
    SELECT user_id, status INTO v_booking_user_id, v_status
    FROM bookings
    WHERE id = p_booking_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Owner check: cannot cancel another user's booking
    IF v_booking_user_id <> p_user_id THEN
        RETURN FALSE;
    END IF;

    -- Only pending bookings can be cancelled by this flow
    IF v_status <> 'pending' THEN
        RETURN FALSE;
    END IF;

    -- Transition booking status to cancelled
    UPDATE bookings
    SET status = 'cancelled', updated_at = clock_timestamp()
    WHERE id = p_booking_id;

    -- Find associated seat IDs and release locks
    SELECT ARRAY_AGG(show_seat_id) INTO v_seat_ids
    FROM booking_seats
    WHERE booking_id = p_booking_id;

    IF v_seat_ids IS NOT NULL AND array_length(v_seat_ids, 1) > 0 THEN
        UPDATE show_seats
        SET status = 'available',
            locked_by = NULL,
            locked_until = NULL,
            updated_at = clock_timestamp()
        WHERE id = ANY(v_seat_ids)
          AND locked_by = p_user_id
          AND status = 'locked';
    END IF;

    RETURN TRUE;
END;
$$;

-- 4. Release individual seat locks directly
CREATE OR REPLACE FUNCTION release_show_seat_locks(
    p_show_seat_ids UUID[],
    p_user_id UUID
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    v_released_count INT;
BEGIN
    UPDATE show_seats
    SET status = 'available',
        locked_by = NULL,
        locked_until = NULL,
        updated_at = clock_timestamp()
    WHERE id = ANY(p_show_seat_ids)
      AND locked_by = p_user_id
      AND status = 'locked';

    GET DIAGNOSTICS v_released_count = ROW_COUNT;
    RETURN v_released_count;
END;
$$;

-- 5. Dev / Payment teammate boundary: confirm_booking_payment
-- Must NEVER be reachable by a normal customer endpoint in production.
CREATE OR REPLACE FUNCTION confirm_booking_payment(
    p_booking_id UUID,
    p_user_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_booking_user_id UUID;
    v_status VARCHAR(20);
    v_expires_at TIMESTAMPTZ;
    v_seat_ids UUID[];
BEGIN
    SELECT user_id, status, expires_at INTO v_booking_user_id, v_status, v_expires_at
    FROM bookings
    WHERE id = p_booking_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF v_booking_user_id <> p_user_id THEN
        RETURN FALSE;
    END IF;

    IF v_status <> 'pending' THEN
        RETURN FALSE;
    END IF;

    IF v_expires_at IS NOT NULL AND v_expires_at < clock_timestamp() THEN
        UPDATE bookings SET status = 'expired', updated_at = clock_timestamp() WHERE id = p_booking_id;
        RETURN FALSE;
    END IF;

    -- Transition booking to confirmed
    UPDATE bookings
    SET status = 'confirmed', updated_at = clock_timestamp()
    WHERE id = p_booking_id;

    -- Transition show seats to booked
    SELECT ARRAY_AGG(show_seat_id) INTO v_seat_ids
    FROM booking_seats
    WHERE booking_id = p_booking_id;

    IF v_seat_ids IS NOT NULL AND array_length(v_seat_ids, 1) > 0 THEN
        UPDATE show_seats
        SET status = 'booked',
            locked_by = NULL,
            locked_until = NULL,
            updated_at = clock_timestamp()
        WHERE id = ANY(v_seat_ids);
    END IF;

    RETURN TRUE;
END;
$$;
