-- ==============================================================================
-- TicketFlow — Reviews: "Report review" + moderation by Manager
-- Run after 005_review_scheduling_and_replies.sql. Safe to run more than once.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.review_reports (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id     uuid NOT NULL REFERENCES public.reviews(id) ON DELETE CASCADE,
    reporter_id   uuid NOT NULL REFERENCES public.users(id)   ON DELETE CASCADE,
    reason        varchar(20) NOT NULL
                      CHECK (reason IN ('spam','abusive','spoiler','off_topic','other')),
    details       text CHECK (details IS NULL OR length(details) <= 500),
    status        varchar(20) NOT NULL DEFAULT 'open'
                      CHECK (status IN ('open','dismissed','reviewed')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    resolved_at   timestamptz,
    resolved_by   uuid REFERENCES public.users(id) ON DELETE SET NULL,
    -- one report per person per review
    CONSTRAINT unique_review_reporter UNIQUE (review_id, reporter_id)
);

CREATE INDEX IF NOT EXISTS idx_review_reports_review_id ON public.review_reports(review_id);
CREATE INDEX IF NOT EXISTS idx_review_reports_status    ON public.review_reports(status);

ALTER TABLE public.review_reports ENABLE ROW LEVEL SECURITY;
