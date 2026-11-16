-- TicketFlow: cached AI review summaries
-- Run this once in the same PostgreSQL/Supabase database used by the backend.

CREATE TABLE IF NOT EXISTS ai_review_summaries (
    event_id UUID PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    audience_summary TEXT NOT NULL,
    critic_summary TEXT NOT NULL,
    overall_summary TEXT NOT NULL,
    audience_liked JSONB NOT NULL DEFAULT '[]'::jsonb,
    audience_disliked JSONB NOT NULL DEFAULT '[]'::jsonb,
    critic_liked JSONB NOT NULL DEFAULT '[]'::jsonb,
    critic_disliked JSONB NOT NULL DEFAULT '[]'::jsonb,
    audience_rating NUMERIC(4,2) NOT NULL DEFAULT 0,
    critic_rating NUMERIC(4,2) NOT NULL DEFAULT 0,
    overall_rating NUMERIC(4,2) NOT NULL DEFAULT 0,
    review_count INTEGER NOT NULL DEFAULT 0,
    source_review_updated_at TIMESTAMPTZ,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_review_summaries_generated_at
    ON ai_review_summaries(generated_at);
