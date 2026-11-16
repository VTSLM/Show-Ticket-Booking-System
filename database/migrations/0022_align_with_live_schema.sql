-- 0022: bring fresh databases in line with the shared Supabase database (schema dump of 2026-11-16).
-- Running this on the shared database changes nothing: it already looks like this.

-- shows.base_price exists in Supabase and is used by browse, manager, seats and dynamic pricing,
-- but no migration created it.
ALTER TABLE public.shows
    ADD COLUMN IF NOT EXISTS base_price numeric(10,2) NOT NULL DEFAULT 0;

-- venues.verification_status: the venue verification code (routers/venue_verification.py,
-- routers/manager.py) writes lowercase values such as 'unverified', 'pending' and 'approved'.
-- 0006 created the column as varchar with an uppercase-only CHECK, which Supabase never had and
-- which rejects those values. Match Supabase: text, default 'unverified', no CHECK.
ALTER TABLE public.venues
    DROP CONSTRAINT IF EXISTS venues_verification_status_check;
ALTER TABLE public.venues
    ALTER COLUMN verification_status TYPE text,
    ALTER COLUMN verification_status SET DEFAULT 'unverified';

-- Row level security is enabled on these tables in Supabase but no migration did it. It blocks
-- Supabase's public REST API (anon key) from reading them. The backend connects as the table
-- owner, which RLS does not restrict, so the app is unaffected.
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.venues ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.screens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.show_seats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.booking_seats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payment_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.venue_case_documents ENABLE ROW LEVEL SECURITY;
