ALTER TABLE venues
    ADD COLUMN IF NOT EXISTS licensed_capacity integer
        CHECK (licensed_capacity IS NULL OR licensed_capacity > 0),
    ADD COLUMN IF NOT EXISTS license_expiry date,
    ADD COLUMN IF NOT EXISTS noc_expiry date;

CREATE TABLE IF NOT EXISTS venue_case_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id uuid NOT NULL
        REFERENCES venue_verification_cases(id) ON DELETE RESTRICT,
    uploaded_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('venue_photo', 'seating_plan')),
    original_filename text NOT NULL,
    content_type text NOT NULL,
    size_bytes integer NOT NULL CHECK (size_bytes > 0),
    storage_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (case_id, kind)
);