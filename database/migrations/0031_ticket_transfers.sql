-- 0031: split and transfer tickets.
-- A booker sends some or all seats of a confirmed booking to another user.
-- The recipient accepts or declines; once accepted the seats get their own QR
-- code (qr_token) and the booking's original QR no longer admits them.
CREATE TABLE IF NOT EXISTS public.ticket_transfers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id uuid NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
    from_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    to_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    recipient_contact varchar(255) NOT NULL,          -- the email or phone the sender typed
    status varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled')),
    qr_token varchar(64) UNIQUE,                       -- set when accepted
    is_used boolean NOT NULL DEFAULT false,
    used_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    responded_at timestamptz,
    CONSTRAINT chk_ticket_transfers_not_self CHECK (from_user_id <> to_user_id),
    CONSTRAINT chk_ticket_transfers_token CHECK (status <> 'accepted' OR qr_token IS NOT NULL),
    CONSTRAINT chk_ticket_transfers_used CHECK (
        (is_used = false AND used_at IS NULL) OR (is_used = true AND used_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS public.ticket_transfer_seats (
    transfer_id uuid NOT NULL REFERENCES public.ticket_transfers(id) ON DELETE CASCADE,
    booking_seat_id uuid NOT NULL REFERENCES public.booking_seats(id) ON DELETE CASCADE,
    PRIMARY KEY (transfer_id, booking_seat_id)
);

CREATE INDEX IF NOT EXISTS idx_ticket_transfers_booking ON public.ticket_transfers (booking_id);
CREATE INDEX IF NOT EXISTS idx_ticket_transfers_to_user ON public.ticket_transfers (to_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticket_transfers_from_user ON public.ticket_transfers (from_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticket_transfer_seats_seat ON public.ticket_transfer_seats (booking_seat_id);

-- The API connects as the database owner, so it is unaffected. With no
-- policies, this blocks direct access through Supabase's public API.
ALTER TABLE public.ticket_transfers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ticket_transfer_seats ENABLE ROW LEVEL SECURITY;
