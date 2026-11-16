-- TicketFlow — Dynamic Seat Pricing (Sprint 2, Tirth)
-- Run in the Supabase SQL editor. Safe to run more than once.
--
-- shows.dynamic_pricing   : manager switch per show (OFF by default, so existing
--                           shows keep their fixed prices).
-- show_seats.price        : stays the fixed base price set when the show is created.
-- show_seats.locked_price : the dynamic price frozen when a customer locks the seat,
--                           so the price they saw is exactly the price they pay.

ALTER TABLE shows      ADD COLUMN IF NOT EXISTS dynamic_pricing boolean NOT NULL DEFAULT false;
ALTER TABLE show_seats ADD COLUMN IF NOT EXISTS locked_price   numeric(10, 2);
