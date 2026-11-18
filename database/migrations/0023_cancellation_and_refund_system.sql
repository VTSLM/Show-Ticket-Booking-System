-- 0023_cancellation_and_refund_system.sql
-- Complete production schema for Booking Cancellation, Refund Management & Notifications

-- 1. Extend bookings table with cancellation reason, notes, charges, refund info
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancellation_reason text;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancellation_notes text;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancellation_charge numeric(10,2) DEFAULT 0.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS refund_amount numeric(10,2) DEFAULT 0.00;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS refund_status varchar(50) DEFAULT 'NOT_APPLICABLE';

-- 2. Refunds table for tracking complete refund lifecycle, attempts, and audit trail
CREATE TABLE IF NOT EXISTS refunds (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    payment_id uuid REFERENCES payments(id) ON DELETE SET NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount numeric(10,2) NOT NULL,
    cancellation_charge numeric(10,2) NOT NULL DEFAULT 0.00,
    currency varchar(10) NOT NULL DEFAULT 'INR',
    status varchar(50) NOT NULL DEFAULT 'PENDING',
    razorpay_payment_id varchar(100),
    razorpay_refund_id varchar(100) UNIQUE,
    failure_reason text,
    retry_count integer NOT NULL DEFAULT 0,
    last_retried_at timestamptz,
    retried_by uuid REFERENCES users(id) ON DELETE SET NULL,
    policy_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_refunds_booking_id ON refunds(booking_id);
CREATE INDEX IF NOT EXISTS idx_refunds_user_id ON refunds(user_id);
CREATE INDEX IF NOT EXISTS idx_refunds_status ON refunds(status);
CREATE INDEX IF NOT EXISTS idx_refunds_rzp_refund_id ON refunds(razorpay_refund_id);

-- 3. Configurable Cancellation Policies (per show or global defaults)
CREATE TABLE IF NOT EXISTS cancellation_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(100) NOT NULL,
    description text,
    cutoff_hours integer NOT NULL DEFAULT 2, -- Must cancel at least cutoff_hours before show start
    deduction_percentage numeric(5,2) NOT NULL DEFAULT 0.00, -- e.g. 10% cancellation charge
    flat_cancellation_fee numeric(10,2) NOT NULL DEFAULT 0.00,
    is_refundable boolean NOT NULL DEFAULT true,
    is_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Insert standard default policy if none exists
INSERT INTO cancellation_policies (name, description, cutoff_hours, deduction_percentage, flat_cancellation_fee, is_refundable, is_default)
SELECT 'Standard Platform Cancellation Policy',
       'Full or partial refund eligible up to 2 hours prior to showtime. Standard 10% cancellation processing charge applies.',
       2, 10.00, 0.00, true, true
WHERE NOT EXISTS (SELECT 1 FROM cancellation_policies WHERE is_default = true);

-- Add policy reference to shows table
ALTER TABLE shows ADD COLUMN IF NOT EXISTS cancellation_policy_id uuid REFERENCES cancellation_policies(id) ON DELETE SET NULL;
