-- 0007: venue verification cases and their audit trail (Sprint 2, venue verification and admin review).
-- These tables were created directly in Supabase and never committed. This file reproduces them
-- exactly from a schema-only dump of the shared database (2026-11-16), so fresh databases match it.
-- Safe to run on the shared database: every statement is guarded.

CREATE TABLE IF NOT EXISTS public.venue_verification_cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    venue_id uuid NOT NULL,
    applicant_id uuid NOT NULL,
    status text DEFAULT 'draft'::text NOT NULL,
    reviewer_id uuid,
    claim_expires_at timestamp with time zone,
    reviewer_comments text,
    version integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT venue_verification_cases_pkey PRIMARY KEY (id),
    CONSTRAINT venue_verification_cases_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'submitted'::text, 'in_review'::text, 'approved'::text, 'rejected'::text, 'changes_requested'::text, 'expired'::text]))),
    CONSTRAINT venue_verification_cases_version_check CHECK ((version > 0)),
    CONSTRAINT venue_verification_cases_venue_id_fkey FOREIGN KEY (venue_id) REFERENCES public.venues(id) ON DELETE RESTRICT,
    CONSTRAINT venue_verification_cases_applicant_id_fkey FOREIGN KEY (applicant_id) REFERENCES public.users(id) ON DELETE RESTRICT,
    CONSTRAINT venue_verification_cases_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_venue_cases_applicant ON public.venue_verification_cases USING btree (applicant_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_venue_cases_queue ON public.venue_verification_cases USING btree (status, created_at);

CREATE TABLE IF NOT EXISTS public.venue_verification_audit (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    case_version integer NOT NULL,
    actor_id uuid NOT NULL,
    action text NOT NULL,
    old_status text NOT NULL,
    new_status text NOT NULL,
    reason text,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT venue_verification_audit_pkey PRIMARY KEY (id),
    CONSTRAINT venue_verification_audit_case_id_case_version_key UNIQUE (case_id, case_version),
    CONSTRAINT venue_verification_audit_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.venue_verification_cases(id) ON DELETE RESTRICT,
    CONSTRAINT venue_verification_audit_actor_id_fkey FOREIGN KEY (actor_id) REFERENCES public.users(id) ON DELETE RESTRICT
);

-- Audit rows are append-only.
CREATE OR REPLACE FUNCTION public.prevent_venue_audit_mutation() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'venue verification audit rows are immutable';
END;
$$;

DROP TRIGGER IF EXISTS venue_audit_no_delete ON public.venue_verification_audit;
CREATE TRIGGER venue_audit_no_delete BEFORE DELETE ON public.venue_verification_audit
    FOR EACH ROW EXECUTE FUNCTION public.prevent_venue_audit_mutation();

DROP TRIGGER IF EXISTS venue_audit_no_update ON public.venue_verification_audit;
CREATE TRIGGER venue_audit_no_update BEFORE UPDATE ON public.venue_verification_audit
    FOR EACH ROW EXECUTE FUNCTION public.prevent_venue_audit_mutation();

-- Block Supabase's public REST API from these tables; the backend connects directly.
ALTER TABLE public.venue_verification_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.venue_verification_audit ENABLE ROW LEVEL SECURITY;
