-- ==============================================================================
-- TicketFlow — Critics Reviews & Ratings Module (Sprint 2 / Feature Addition)
-- Run after migrations 001_initial_schema.sql and 002_payment_gateway.sql.
-- Safe to run multiple times (idempotent).
-- ==============================================================================

-- 1. Extend Users table for Critic profiles
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS is_verified boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS publication varchar(255),
ADD COLUMN IF NOT EXISTS avatar_url text,
ADD COLUMN IF NOT EXISTS bio text;

-- 2. Register 'critic' role in roles catalog
INSERT INTO public.roles (code, name) VALUES
    ('critic', 'Verified Film Critic')
ON CONFLICT (code) DO NOTHING;

-- 3. Main Reviews Table
CREATE TABLE IF NOT EXISTS public.reviews (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        uuid NOT NULL REFERENCES public.events(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rating          numeric(3,1) NOT NULL CHECK (rating >= 1.0 AND rating <= 10.0),
    headline        varchar(255) NOT NULL,
    content         text NOT NULL,
    sections_json   jsonb,                        -- Structured sub-sections: Story, Direction, Performances, etc. (FR-09)
    media_url       text,                         -- Attached trailer/image clip (FR-14)
    is_spoiler      boolean NOT NULL DEFAULT false, -- Blurred spoiler flag (FR-12, FR-13)
    version         integer NOT NULL DEFAULT 1,   -- Version number (FR-28)
    published_at    timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT unique_event_user_review UNIQUE (event_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_event_id ON public.reviews(event_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON public.reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_published_at ON public.reviews(published_at DESC);

-- 4. Review Upvotes Table (FR-20)
CREATE TABLE IF NOT EXISTS public.review_upvotes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id       uuid NOT NULL REFERENCES public.reviews(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT unique_review_user_upvote UNIQUE (review_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_review_upvotes_review_id ON public.review_upvotes(review_id);

-- 5. Reader Comments Table (FR-18, FR-19)
CREATE TABLE IF NOT EXISTS public.review_comments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id       uuid NOT NULL REFERENCES public.reviews(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    content         text NOT NULL CHECK (length(trim(content)) > 0),
    is_pinned       boolean NOT NULL DEFAULT false, -- Critic pinning (FR-19)
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_comments_review_id ON public.review_comments(review_id);

-- 6. Review Revision & Version History Table (FR-28, FR-29, NFR-16)
CREATE TABLE IF NOT EXISTS public.review_versions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id       uuid NOT NULL REFERENCES public.reviews(id) ON DELETE CASCADE,
    version_number  integer NOT NULL,
    rating          numeric(3,1) NOT NULL,
    headline        varchar(255) NOT NULL,
    content         text NOT NULL,
    sections_json   jsonb,
    is_spoiler      boolean NOT NULL DEFAULT false,
    change_summary  varchar(255),
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT unique_review_version UNIQUE (review_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_review_versions_review_id ON public.review_versions(review_id);

-- 7. Enable Row Level Security (matches TicketFlow pattern)
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_upvotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.review_versions ENABLE ROW LEVEL SECURITY;
