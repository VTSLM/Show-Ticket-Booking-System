-- Person B: venue/listing verification, case engine, audit trail.
-- Run after the existing sprint1_v2 schema.
-- Keep shared enums and table ownership aligned with the approved contract.

ALTER TABLE public.venues
    ADD COLUMN IF NOT EXISTS verification_status varchar(30)
        NOT NULL DEFAULT 'DRAFT';

ALTER TABLE public.venues
    DROP CONSTRAINT IF EXISTS venues_verification_status_check;

ALTER TABLE public.venues
    ADD CONSTRAINT venues_verification_status_check
        CHECK (verification_status IN (
            'DRAFT', 'SUBMITTED', 'IN_REVIEW', 'CHANGES_REQUESTED',
            'APPROVED', 'REJECTED', 'SUSPENDED', 'EXPIRED'
        ));

CREATE TABLE IF NOT EXISTS public.verification_cases (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_type           varchar(20) NOT NULL
                            CHECK (case_type IN ('ORGANIZER', 'VENUE', 'LISTING')),
    -- Polymorphic subject: venue id, organizer profile id, or listing/event id.
    -- The subject is not a foreign key because these entities have different tables.
    subject_id          uuid NOT NULL,
    applicant_user_id   uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    status              varchar(30) NOT NULL DEFAULT 'DRAFT'
                            CHECK (status IN (
                                'DRAFT', 'SUBMITTED', 'IN_REVIEW',
                                'CHANGES_REQUESTED', 'APPROVED', 'REJECTED',
                                'SUSPENDED', 'EXPIRED'
                            )),
    submitted_at        timestamptz,
    claimed_by          uuid REFERENCES public.users(id) ON DELETE SET NULL,
    claim_expires_at    timestamptz,
    decided_by          uuid REFERENCES public.users(id) ON DELETE SET NULL,
    decided_at          timestamptz,
    decision_reason     text,
    row_version         integer NOT NULL DEFAULT 1 CHECK (row_version > 0),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CHECK ((claimed_by IS NULL) = (claim_expires_at IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_verification_cases_queue
    ON public.verification_cases (status, submitted_at);

CREATE INDEX IF NOT EXISTS idx_verification_cases_applicant
    ON public.verification_cases (applicant_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verification_cases_claim
    ON public.verification_cases (claim_expires_at)
    WHERE status = 'IN_REVIEW';

-- Prevent multiple simultaneously active cases for the same subject.
CREATE UNIQUE INDEX IF NOT EXISTS uq_verification_cases_active_subject
    ON public.verification_cases (case_type, subject_id)
    WHERE status IN ('SUBMITTED', 'IN_REVIEW', 'CHANGES_REQUESTED');

CREATE TABLE IF NOT EXISTS public.venue_compliance (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id            uuid NOT NULL UNIQUE
                            REFERENCES public.venues(id) ON DELETE CASCADE,
    applicant_user_id   uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    licence_no_masked   varchar(30),
    licence_hash        varchar(128),
    licence_authority   varchar(200),
    licence_valid_to    date,
    fire_noc_valid_to   date,
    electrical_valid_to date,
    licensed_capacity  integer NOT NULL CHECK (licensed_capacity > 0),
    ownership_type      varchar(30) NOT NULL
                            CHECK (ownership_type IN ('OWNER', 'LEASE', 'MANAGER')),
    ownership_doc_id    uuid,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_venue_compliance_expiry
    ON public.venue_compliance (licence_valid_to);

CREATE TABLE IF NOT EXISTS public.listing_reviews (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        uuid NOT NULL REFERENCES public.events(id) ON DELETE RESTRICT,
    show_id         uuid REFERENCES public.shows(id) ON DELETE RESTRICT,
    status          varchar(30) NOT NULL DEFAULT 'SUBMITTED'
                        CHECK (status IN (
                            'SUBMITTED', 'IN_REVIEW', 'CHANGES_REQUESTED',
                            'APPROVED', 'REJECTED', 'FLAGGED', 'REMOVED'
                        )),
    reviewer_id     uuid REFERENCES public.users(id) ON DELETE SET NULL,
    reason          text,
    conflict_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    reviewed_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_listing_reviews_queue
    ON public.listing_reviews (status, created_at);

CREATE TABLE IF NOT EXISTS public.listing_reports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        uuid NOT NULL REFERENCES public.events(id) ON DELETE RESTRICT,
    reported_by     uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    reason_code     varchar(40) NOT NULL,
    note            text,
    status          varchar(20) NOT NULL DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_listing_reports_queue
    ON public.listing_reports (status, created_at);

CREATE TABLE IF NOT EXISTS public.audit_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        uuid REFERENCES public.users(id) ON DELETE SET NULL,
    actor_role      varchar(50) NOT NULL,
    action          varchar(100) NOT NULL,
    entity_type     varchar(50) NOT NULL,
    entity_id       uuid NOT NULL,
    before          jsonb,
    after           jsonb,
    reason          text NOT NULL DEFAULT '',
    at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_entity
    ON public.audit_log (entity_type, entity_id, at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON public.audit_log (actor_id, at DESC);

CREATE TABLE IF NOT EXISTS public.checklist_templates (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_type               varchar(20) NOT NULL
                                CHECK (case_type IN ('ORGANIZER', 'VENUE', 'LISTING')),
    state                   varchar(100) NOT NULL DEFAULT '*',
    required_document_types jsonb NOT NULL DEFAULT '[]'::jsonb,
    validity_rules          jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_by              uuid REFERENCES public.users(id) ON DELETE SET NULL,
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (case_type, state)
);

ALTER TABLE public.verification_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.venue_compliance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.listing_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.listing_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.checklist_templates ENABLE ROW LEVEL SECURITY;

-- Audit rows are append-only for application users. Also enforce this at
-- the database layer so a mistaken endpoint cannot rewrite audit history.
CREATE OR REPLACE FUNCTION public.reject_audit_log_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_log_no_update_delete ON public.audit_log;

CREATE TRIGGER trg_audit_log_no_update_delete
BEFORE UPDATE OR DELETE ON public.audit_log
FOR EACH ROW EXECUTE FUNCTION public.reject_audit_log_mutation();