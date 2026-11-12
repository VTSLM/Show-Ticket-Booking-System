-- TicketFlow — Ticket Cancellation & Refund (Sprint 2)
-- Run in Supabase SQL editor AFTER unified_schema.sql and 003_customer_care.sql.
-- Safe to run more than once.

-- Track when a booking was cancelled
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cancelled_at timestamptz;

-- Track Razorpay refund details on the payments row
ALTER TABLE payments ADD COLUMN IF NOT EXISTS razorpay_refund_id varchar(100);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS refunded_amount   numeric(10,2);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS refunded_at       timestamptz;
