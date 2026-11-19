-- 0023: FIFO waitlist for sold-out shows.
CREATE TABLE IF NOT EXISTS public.show_waitlist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    show_id uuid NOT NULL REFERENCES public.shows(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_show_waitlist_show_user UNIQUE (show_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_show_waitlist_fifo
    ON public.show_waitlist (show_id, created_at, id)
    WHERE status = 'waiting';

CREATE INDEX IF NOT EXISTS idx_show_waitlist_user
    ON public.show_waitlist (user_id, created_at DESC)
    WHERE status = 'waiting';
