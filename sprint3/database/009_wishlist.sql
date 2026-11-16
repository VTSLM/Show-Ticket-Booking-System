-- 009: Wishlist — users can save events (movies / concerts / plays) to watch later.
-- Run in the Supabase SQL editor after 008.

CREATE TABLE IF NOT EXISTS public.wishlists (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES public.users(id)  ON DELETE CASCADE,
    event_id    uuid NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_wishlists_user ON public.wishlists (user_id, created_at DESC);

ALTER TABLE public.wishlists ENABLE ROW LEVEL SECURITY;
