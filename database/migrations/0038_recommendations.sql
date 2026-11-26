-- 0038: personalized recommendations (#218, Registered user FR2, FR3).
--  * user_preferences: favourite genres, artists and cities set on the profile page.
--  * event_views: which published events a logged-in user opened, one row per user and event,
--    so browsing behaviour can feed the recommendations.
CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    genres text[] NOT NULL DEFAULT '{}',
    artists text[] NOT NULL DEFAULT '{}',
    cities text[] NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.event_views (
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    event_id uuid NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    view_count integer NOT NULL DEFAULT 1 CHECK (view_count > 0),
    first_viewed_at timestamptz NOT NULL DEFAULT now(),
    last_viewed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);
CREATE INDEX IF NOT EXISTS idx_event_views_recent
    ON public.event_views (user_id, last_viewed_at DESC);
ALTER TABLE public.event_views ENABLE ROW LEVEL SECURITY;

-- Trending counts recent confirmed bookings per event
CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON public.bookings (created_at);
