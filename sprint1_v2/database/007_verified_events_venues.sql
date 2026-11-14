-- Migration 007: Verified Events & Multi-Venue Verification Guards
-- 1. Relax organizer_profiles UNIQUE constraint to support multiple organizations per user account
ALTER TABLE organizer_profiles DROP CONSTRAINT IF EXISTS organizer_profiles_user_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_organizer_profiles_user_legal_name 
    ON organizer_profiles(user_id, legal_name);

-- 2. Link events to host organizer profiles
ALTER TABLE events 
    ADD COLUMN IF NOT EXISTS organizer_id uuid REFERENCES organizer_profiles(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_events_organizer_id ON events(organizer_id);

-- 3. Backfill existing events to ensure backward compatibility with existing seeds & tests
DO $$
DECLARE
    v_default_org_id uuid;
    v_admin_user_id uuid;
BEGIN
    -- Find an approved organizer profile or admin user
    SELECT id INTO v_default_org_id FROM organizer_profiles WHERE verification_status = 'APPROVED' LIMIT 1;

    IF v_default_org_id IS NULL THEN
        -- Find or use the first user
        SELECT id INTO v_admin_user_id FROM users LIMIT 1;
        IF v_admin_user_id IS NOT NULL THEN
            INSERT INTO organizer_profiles (user_id, legal_name, business_type, verification_status, trust_tier)
            VALUES (v_admin_user_id, 'Official Showcase Entertainment', 'COMPANY', 'APPROVED', 'TIER_1')
            ON CONFLICT DO NOTHING
            RETURNING id INTO v_default_org_id;
            
            IF v_default_org_id IS NULL THEN
                SELECT id INTO v_default_org_id FROM organizer_profiles WHERE legal_name = 'Official Showcase Entertainment' LIMIT 1;
            END IF;
        END IF;
    END IF;

    -- Link orphan events to default approved organizer
    IF v_default_org_id IS NOT NULL THEN
        UPDATE events SET organizer_id = v_default_org_id WHERE organizer_id IS NULL;
    END IF;

    -- Mark core verified venues as 'approved' if they are still 'unverified'
    UPDATE venues SET verification_status = 'approved' 
    WHERE name IN ('Narendra Modi Stadium', 'Royal Proscenium Auditorium', 'Main Concert Arena & Grounds', 'Galaxy, Mumbai', 'PVR', 'Palladium');
END $$;

