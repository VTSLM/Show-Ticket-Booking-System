-- 0003: user birthdate, unified tickets and receipts tables, base roles.
-- Originally sprint1_v2/database/unified_schema.sql (Sprint 1 integration).
-- Replaces the denormalised tickets table from the standalone Sprint 1 ticket module.

-- ===================== STEP 2.5: User Birthdate =====================
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS birthdate date;
-- ===================== STEP 3: Unified Tickets Table =====================
-- Simplified tickets table that integrates with the booking system
CREATE TABLE IF NOT EXISTS tickets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      uuid NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    show_id         uuid NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    qr_code_data    text NOT NULL,
    status          varchar(20) NOT NULL DEFAULT 'valid'
                        CHECK (status IN ('valid','used','cancelled')),
    is_used         boolean NOT NULL DEFAULT false,
    used_at         timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (booking_id),
    CHECK ((is_used = false AND used_at IS NULL) OR (is_used = true AND used_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_tickets_booking_id ON tickets(booking_id);
CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_qr_code ON tickets(qr_code_data);

-- Receipts table (may already exist from 001 schema)
CREATE TABLE IF NOT EXISTS receipts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      uuid NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    receipt_number  varchar(100) NOT NULL UNIQUE,
    issued_at       timestamptz NOT NULL DEFAULT now()
);

-- Seed roles
INSERT INTO roles (code, name) VALUES
    ('customer', 'Customer'),
    ('manager', 'Manager'),
    ('admin', 'Administrator')
ON CONFLICT (code) DO NOTHING;

-- Create a default admin user (optional - set firebase_uid manually after first Firebase sign-in)
-- You can add this after registering an admin via Firebase, then:
-- UPDATE users SET status='active' WHERE email='admin@yourproject.com';
-- INSERT INTO user_roles (user_id, role_id)
--   SELECT u.id, r.id FROM users u, roles r WHERE u.email='admin@yourproject.com' AND r.code='admin';
