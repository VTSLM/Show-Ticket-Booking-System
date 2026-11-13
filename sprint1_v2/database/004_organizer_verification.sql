-- ==============================================================================
-- TicketFlow — Sprint 2: Organizer Verification & Shared Admin Foundations
-- Migration: 004_organizer_verification.sql
--
-- Deliverable: Person A A-01 (Foundation)
-- Shared with: Person B (Venue Verification)
--
-- Tables created:
--   1. trust_tier_rules         (configurable organizer trust tiers)
--   2. organizer_profiles       (organizer business and legal identity)
--   3. bank_accounts            (tokenized/hashed bank accounts for settlements)
--   4. verification_documents   (shared polymorphic document registry)
--   5. duplicate_fingerprints   (shared collision detection / anti-fraud store)
--   6. notifications            (shared user notification events)
-- ==============================================================================

-- 1. Trust Tier Rules
CREATE TABLE IF NOT EXISTS trust_tier_rules (
    tier                varchar(50) PRIMARY KEY,
    max_live_shows      integer NOT NULL DEFAULT 1 CHECK (max_live_shows >= 0),
    payout_hold_days    integer NOT NULL DEFAULT 7 CHECK (payout_hold_days >= 0),
    rules               jsonb NOT NULL DEFAULT '{}'::jsonb,
    description         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Seed baseline trust tiers
INSERT INTO trust_tier_rules (tier, max_live_shows, payout_hold_days, rules, description)
VALUES
    ('TIER_1', 2, 14, '{"instant_payout": false, "ticket_price_limit": 5000, "security_deposit_required": false}'::jsonb, 'Standard starter tier for newly approved organizers'),
    ('TIER_2', 10, 7, '{"instant_payout": false, "ticket_price_limit": 25000, "security_deposit_required": false}'::jsonb, 'Intermediate tier for established organizers with clean history'),
    ('TIER_3', 50, 3, '{"instant_payout": true, "ticket_price_limit": 100000, "security_deposit_required": false}'::jsonb, 'High-volume trusted tier with expedited settlement')
ON CONFLICT (tier) DO NOTHING;


-- 2. Organizer Profiles
CREATE TABLE IF NOT EXISTS organizer_profiles (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    legal_name          varchar(255) NOT NULL,
    business_type       varchar(50) NOT NULL
                            CHECK (business_type IN ('INDIVIDUAL', 'SOLE_PROPRIETOR', 'COMPANY', 'LLP', 'TRUST')),
    state               varchar(100),
    pan_masked          varchar(20),
    gstin_masked        varchar(20),
    verification_status varchar(30) NOT NULL DEFAULT 'PENDING'
                            CHECK (verification_status IN ('DRAFT', 'SUBMITTED', 'IN_REVIEW', 'PENDING', 'CHANGES_REQUESTED', 'APPROVED', 'REJECTED', 'SUSPENDED', 'EXPIRED')),
    trust_tier          varchar(50) NOT NULL DEFAULT 'TIER_1' REFERENCES trust_tier_rules(tier) ON DELETE RESTRICT,
    reviewer_id         uuid REFERENCES users(id) ON DELETE SET NULL,
    claimed_at          timestamptz,
    claim_expires_at    timestamptz,
    reviewer_comments   text,
    rejection_reason    text,
    suspension_reason   text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_organizer_profiles_user_id ON organizer_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_organizer_profiles_verification_status ON organizer_profiles(verification_status);
CREATE INDEX IF NOT EXISTS idx_organizer_profiles_business_type ON organizer_profiles(business_type);


-- 3. Bank Accounts (Sensitive numbers never stored plaintext)
CREATE TABLE IF NOT EXISTS bank_accounts (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organizer_id        uuid NOT NULL REFERENCES organizer_profiles(id) ON DELETE CASCADE,
    holder_name         varchar(255) NOT NULL,
    ifsc                varchar(20) NOT NULL,
    account_masked      varchar(30) NOT NULL,
    account_hash        varchar(128) NOT NULL,
    verified            boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bank_accounts_organizer_id ON bank_accounts(organizer_id);
CREATE INDEX IF NOT EXISTS idx_bank_accounts_account_hash ON bank_accounts(account_hash);


-- 4. Verification Documents (Shared Foundation for Organizer & Person B Venue / Listing)
CREATE TABLE IF NOT EXISTS verification_documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             uuid NOT NULL,
    case_type           varchar(30) NOT NULL
                            CHECK (case_type IN ('ORGANIZER', 'VENUE', 'LISTING')),
    doc_type            varchar(50) NOT NULL
                            CHECK (doc_type IN (
                                'PAN', 'GST_CERTIFICATE', 'BANK_PROOF', 'SIGNATORY_ID',
                                'AUTHORISATION_LETTER', 'BUSINESS_REGISTRATION',
                                'CINEMA_LICENCE', 'FIRE_NOC', 'ELECTRICAL_CERT',
                                'OCCUPANCY_CERT', 'OWNERSHIP_PROOF', 'OTHER'
                            )),
    version             integer NOT NULL DEFAULT 1 CHECK (version > 0),
    storage_ref         text NOT NULL,
    doc_number_masked   varchar(50),
    issued_by           varchar(255),
    valid_to            date,
    review_status       varchar(30) NOT NULL DEFAULT 'PENDING'
                            CHECK (review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED')),
    reviewer_comment    text,
    uploaded_by         uuid REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at         timestamptz NOT NULL DEFAULT now(),
    reviewed_by         uuid REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at         timestamptz
);

CREATE INDEX IF NOT EXISTS idx_verification_docs_case ON verification_documents(case_id, case_type);
CREATE INDEX IF NOT EXISTS idx_verification_docs_case_doc ON verification_documents(case_id, doc_type, version DESC);
CREATE INDEX IF NOT EXISTS idx_verification_docs_review_status ON verification_documents(review_status);
CREATE INDEX IF NOT EXISTS idx_verification_docs_doc_type ON verification_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_verification_docs_uploaded_by ON verification_documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_verification_docs_reviewed_by ON verification_documents(reviewed_by);


-- 5. Duplicate Fingerprints (Shared Anti-fraud Store for Person A & Person B)
CREATE TABLE IF NOT EXISTS duplicate_fingerprints (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind                varchar(50) NOT NULL,
    salted_hash         varchar(128) NOT NULL,
    case_id             uuid NOT NULL,
    case_type           varchar(30) NOT NULL DEFAULT 'ORGANIZER'
                            CHECK (case_type IN ('ORGANIZER', 'VENUE', 'LISTING')),
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, salted_hash)
);

CREATE INDEX IF NOT EXISTS idx_dup_fingerprints_case ON duplicate_fingerprints(case_id, case_type);


-- 6. Notifications (Shared notification foundation)
CREATE TABLE IF NOT EXISTS notifications (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_name          varchar(100) NOT NULL,
    payload             jsonb NOT NULL DEFAULT '{}'::jsonb,
    read_at             timestamptz,
    emailed_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, created_at DESC) WHERE read_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_notifications_read_at ON notifications(read_at);


-- 7. Trigger attachments for updated_at timestamps
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'set_updated_at') THEN
        DROP TRIGGER IF EXISTS trg_trust_tier_rules_updated_at ON trust_tier_rules;
        CREATE TRIGGER trg_trust_tier_rules_updated_at BEFORE UPDATE ON trust_tier_rules FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        DROP TRIGGER IF EXISTS trg_organizer_profiles_updated_at ON organizer_profiles;
        CREATE TRIGGER trg_organizer_profiles_updated_at BEFORE UPDATE ON organizer_profiles FOR EACH ROW EXECUTE FUNCTION set_updated_at();

        DROP TRIGGER IF EXISTS trg_bank_accounts_updated_at ON bank_accounts;
        CREATE TRIGGER trg_bank_accounts_updated_at BEFORE UPDATE ON bank_accounts FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;


-- 8. Row Level Security
ALTER TABLE trust_tier_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE duplicate_fingerprints ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

