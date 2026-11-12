-- TicketFlow — Archive of deleted reviews
-- Run once in the Supabase SQL editor. Safe to run more than once.
--
-- Why: reviews / review_versions / review_comments use ON DELETE CASCADE, so
-- deleting a review would wipe its history. Before a review is deleted the
-- backend now copies it (with every earlier version and its comments) into
-- this table.
--
-- No foreign keys on purpose: the archive must survive even if the original
-- review, event or user row is removed later.

CREATE TABLE IF NOT EXISTS public.review_deletions (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id         uuid NOT NULL,            -- id the review had before deletion
    event_id          uuid NOT NULL,
    user_id           uuid NOT NULL,            -- review author
    rating            numeric(3,1) NOT NULL,
    headline          varchar(255) NOT NULL,
    content           text NOT NULL,
    sections_json     jsonb,
    media_url         text,
    is_spoiler        boolean NOT NULL DEFAULT false,
    version           integer NOT NULL,         -- version number at time of deletion
    published_at      timestamptz NOT NULL,
    last_updated_at   timestamptz NOT NULL,
    versions_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,  -- every earlier version
    comments_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb,  -- comments on the review
    upvotes_count     integer NOT NULL DEFAULT 0,
    deleted_by        uuid,                     -- who deleted it (author or admin)
    deleted_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_deletions_event_id ON public.review_deletions(event_id);
CREATE INDEX IF NOT EXISTS idx_review_deletions_user_id  ON public.review_deletions(user_id);

ALTER TABLE public.review_deletions ENABLE ROW LEVEL SECURITY;
