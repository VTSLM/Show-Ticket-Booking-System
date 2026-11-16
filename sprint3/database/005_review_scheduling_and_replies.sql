-- ==============================================================================
-- TicketFlow — Reviews: scheduled publishing + threaded replies
-- Run after 003_reviews_module.sql and 004_review_deletions.sql.
-- Safe to run multiple times (idempotent).
-- ==============================================================================

-- 1. Scheduled publishing
--    reviews.scheduled_for already exists in 003; this is only a safety net.
ALTER TABLE public.reviews
    ADD COLUMN IF NOT EXISTS scheduled_for timestamptz;

-- A review is PUBLIC when:  is_draft = false
--                      AND (scheduled_for IS NULL OR scheduled_for <= now())
-- No cron job is needed: the API simply hides reviews whose time has not come.
CREATE INDEX IF NOT EXISTS idx_reviews_scheduled_for
    ON public.reviews(scheduled_for)
    WHERE scheduled_for IS NOT NULL;

-- 2. Threaded replies on review comments
--    parent_comment_id IS NULL      -> top-level comment
--    parent_comment_id = <comment>  -> reply (one level deep; the API flattens deeper replies)
ALTER TABLE public.review_comments
    ADD COLUMN IF NOT EXISTS parent_comment_id uuid
        REFERENCES public.review_comments(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_review_comments_parent
    ON public.review_comments(parent_comment_id);
