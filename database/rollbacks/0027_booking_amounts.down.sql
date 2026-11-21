-- Reverses 0027_booking_amounts.sql. Do not run on the live database: the booking code
-- writes these columns.
ALTER TABLE public.bookings DROP COLUMN IF EXISTS coupon_id;
ALTER TABLE public.bookings DROP COLUMN IF EXISTS discount_amount;
ALTER TABLE public.bookings DROP COLUMN IF EXISTS subtotal_amount;
