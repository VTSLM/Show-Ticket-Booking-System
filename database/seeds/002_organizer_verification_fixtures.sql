-- ==============================================================================
-- TicketFlow — Sprint 2: Organizer Verification Fixtures
-- File: 002_organizer_verification_fixtures.sql
--
-- Provides 6 required sample organizer personas using fictional data:
--   1. Individual Organizer (Rahul Sharma - INDIVIDUAL, DRAFT)
--   2. Sole Proprietor (Priya Patel Events - SOLE_PROPRIETOR, APPROVED)
--   3. Company (Skyline Entertainment Pvt Ltd - COMPANY, APPROVED, TIER_3)
--   4. Awaiting Verification (Aarav Live Productions - INDIVIDUAL, PENDING)
--   5. Approved Organizer (Apex Shows LLP - LLP, APPROVED, TIER_2)
--   6. Application Needs Changes (Kavita Art Foundation - TRUST, CHANGES_REQUESTED)
-- ==============================================================================

-- 1. Create fictional user accounts for the organizers
INSERT INTO users (firebase_uid, name, email, phone, status)
VALUES
    ('FIXTURE_UID_ORG_INDIVIDUAL', 'Rahul Sharma', 'rahul.individual@fixture.example.com', '+919876500001', 'active'),
    ('FIXTURE_UID_ORG_SOLE_PROP', 'Priya Patel', 'priya.soleprop@fixture.example.com', '+919876500002', 'active'),
    ('FIXTURE_UID_ORG_COMPANY', 'Skyline Admin', 'admin@skyline-events.fixture.com', '+919876500003', 'active'),
    ('FIXTURE_UID_ORG_PENDING', 'Aarav Mehta', 'aarav.pending@fixture.example.com', '+919876500004', 'inactive'),
    ('FIXTURE_UID_ORG_APPROVED', 'Apex Live Director', 'director@apex-shows.fixture.com', '+919876500005', 'active'),
    ('FIXTURE_UID_ORG_CHANGES_REQ', 'Kavita Trust Secretary', 'secretary@kavita-arts.fixture.org', '+919876500006', 'inactive')
ON CONFLICT (firebase_uid) DO NOTHING;

-- Assign manager roles to the organizer users
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.email IN (
    'rahul.individual@fixture.example.com',
    'priya.soleprop@fixture.example.com',
    'admin@skyline-events.fixture.com',
    'aarav.pending@fixture.example.com',
    'director@apex-shows.fixture.com',
    'secretary@kavita-arts.fixture.org'
)
AND r.code = 'manager'
ON CONFLICT DO NOTHING;


-- 2. Insert Organizer Profiles
-- Persona 1: Individual Organizer
INSERT INTO organizer_profiles (user_id, legal_name, business_type, state, pan_masked, gstin_masked, verification_status, trust_tier)
SELECT u.id, 'Rahul Sharma', 'INDIVIDUAL', 'Maharashtra', 'ABCDE****R', NULL, 'DRAFT', 'TIER_1'
FROM users u WHERE u.email = 'rahul.individual@fixture.example.com'
ON CONFLICT (user_id) DO NOTHING;

-- Persona 2: Sole Proprietor
INSERT INTO organizer_profiles (user_id, legal_name, business_type, state, pan_masked, gstin_masked, verification_status, trust_tier)
SELECT u.id, 'Priya Patel Events', 'SOLE_PROPRIETOR', 'Gujarat', 'ABCPD****P', '24ABCPD****1Z3', 'APPROVED', 'TIER_1'
FROM users u WHERE u.email = 'priya.soleprop@fixture.example.com'
ON CONFLICT (user_id) DO NOTHING;

-- Persona 3: Company
INSERT INTO organizer_profiles (user_id, legal_name, business_type, state, pan_masked, gstin_masked, verification_status, trust_tier)
SELECT u.id, 'Skyline Entertainment Private Limited', 'COMPANY', 'Karnataka', 'AAACS****C', '29AAACS****2Z8', 'APPROVED', 'TIER_3'
FROM users u WHERE u.email = 'admin@skyline-events.fixture.com'
ON CONFLICT (user_id) DO NOTHING;

-- Persona 4: Organizer Awaiting Verification
INSERT INTO organizer_profiles (user_id, legal_name, business_type, state, pan_masked, gstin_masked, verification_status, trust_tier)
SELECT u.id, 'Aarav Mehta Productions', 'INDIVIDUAL', 'Delhi', 'ABCPM****M', NULL, 'PENDING', 'TIER_1'
FROM users u WHERE u.email = 'aarav.pending@fixture.example.com'
ON CONFLICT (user_id) DO NOTHING;

-- Persona 5: Approved Organizer (LLP)
INSERT INTO organizer_profiles (user_id, legal_name, business_type, state, pan_masked, gstin_masked, verification_status, trust_tier)
SELECT u.id, 'Apex Live Events LLP', 'LLP', 'Maharashtra', 'AAACL****L', '27AAACL****1Z4', 'APPROVED', 'TIER_2'
FROM users u WHERE u.email = 'director@apex-shows.fixture.com'
ON CONFLICT (user_id) DO NOTHING;

-- Persona 6: Organizer Whose Application Needs Changes
INSERT INTO organizer_profiles (user_id, legal_name, business_type, state, pan_masked, gstin_masked, verification_status, trust_tier)
SELECT u.id, 'Kavita Art Foundation Trust', 'TRUST', 'Rajasthan', 'AAATK****T', NULL, 'CHANGES_REQUESTED', 'TIER_1'
FROM users u WHERE u.email = 'secretary@kavita-arts.fixture.org'
ON CONFLICT (user_id) DO NOTHING;


-- 3. Insert Bank Accounts (Masked + SHA-256 salted account hash)
INSERT INTO bank_accounts (organizer_id, holder_name, ifsc, account_masked, account_hash, verified)
SELECT op.id, 'Priya Patel', 'HDFC0001234', '********4589', '8a6d71f6520ad961b12b50f75a7f0e8f416d8a7c2937e0c4519962e21b7e9001', true
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'priya.soleprop@fixture.example.com'
AND NOT EXISTS (SELECT 1 FROM bank_accounts ba WHERE ba.organizer_id = op.id);

INSERT INTO bank_accounts (organizer_id, holder_name, ifsc, account_masked, account_hash, verified)
SELECT op.id, 'Skyline Entertainment Pvt Ltd', 'ICIC0000987', '********9012', '9b7e82a7631be072c23c61a86b8a1f9a527e9b8d3048f1d5620073f32c8f0112', true
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'admin@skyline-events.fixture.com'
AND NOT EXISTS (SELECT 1 FROM bank_accounts ba WHERE ba.organizer_id = op.id);

INSERT INTO bank_accounts (organizer_id, holder_name, ifsc, account_masked, account_hash, verified)
SELECT op.id, 'Apex Live Events LLP', 'KKBK0004567', '********3344', '1c8f93b8742cf183d34d72b97c9b2a0b638f0c9e4159a2e6731184a43d9a1223', true
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'director@apex-shows.fixture.com'
AND NOT EXISTS (SELECT 1 FROM bank_accounts ba WHERE ba.organizer_id = op.id);


-- 4. Verification Documents (Covering various doc_types and review statuses)
-- Documents for Aarav Live (Pending)
INSERT INTO verification_documents (case_id, case_type, doc_type, version, storage_ref, doc_number_masked, issued_by, review_status, uploaded_by)
SELECT op.id, 'ORGANIZER', 'PAN', 1, 'vault/organizers/aarav_mehta/pan_v1.pdf', 'ABCPM****M', 'Income Tax Department', 'PENDING', op.user_id
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'aarav.pending@fixture.example.com'
AND NOT EXISTS (SELECT 1 FROM verification_documents vd WHERE vd.case_id = op.id AND vd.doc_type = 'PAN');

-- Documents for Kavita Art Foundation (Needs Changes)
INSERT INTO verification_documents (case_id, case_type, doc_type, version, storage_ref, doc_number_masked, issued_by, review_status, reviewer_comment, uploaded_by)
SELECT op.id, 'ORGANIZER', 'BUSINESS_REGISTRATION', 1, 'vault/organizers/kavita_trust/trust_deed_v1.pdf', 'REG-1998-****', 'Charity Commissioner', 'CHANGES_REQUESTED', 'Uploaded copy is blurry. Please provide a clear scanned copy of page 3 with trustee signatures.', op.user_id
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'secretary@kavita-arts.fixture.org'
AND NOT EXISTS (SELECT 1 FROM verification_documents vd WHERE vd.case_id = op.id AND vd.doc_type = 'BUSINESS_REGISTRATION');

-- Documents for Apex Shows LLP (Approved)
INSERT INTO verification_documents (case_id, case_type, doc_type, version, storage_ref, doc_number_masked, issued_by, review_status, reviewer_comment, uploaded_by)
SELECT op.id, 'ORGANIZER', 'GST_CERTIFICATE', 1, 'vault/organizers/apex_llp/gstin_cert_v1.pdf', '27AAACL****1Z4', 'GSTN Council', 'APPROVED', 'Verified against GST portal.', op.user_id
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'director@apex-shows.fixture.com'
AND NOT EXISTS (SELECT 1 FROM verification_documents vd WHERE vd.case_id = op.id AND vd.doc_type = 'GST_CERTIFICATE');


-- 5. Duplicate Fingerprints (Salted hash collision store)
INSERT INTO duplicate_fingerprints (kind, salted_hash, case_id, case_type)
SELECT 'PAN', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', op.id, 'ORGANIZER'
FROM organizer_profiles op
JOIN users u ON u.id = op.user_id
WHERE u.email = 'director@apex-shows.fixture.com'
ON CONFLICT (kind, salted_hash) DO NOTHING;


-- 6. Notifications
INSERT INTO notifications (user_id, event_name, payload)
SELECT u.id, 'organizer.application_submitted', '{"message": "Your organizer verification application has been submitted for administrative review.", "case_type": "ORGANIZER"}'::jsonb
FROM users u WHERE u.email = 'aarav.pending@fixture.example.com'
AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.user_id = u.id AND n.event_name = 'organizer.application_submitted');

INSERT INTO notifications (user_id, event_name, payload)
SELECT u.id, 'organizer.changes_requested', '{"message": "Action required: Please update your business registration document.", "comment": "Uploaded copy is blurry."}'::jsonb
FROM users u WHERE u.email = 'secretary@kavita-arts.fixture.org'
AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.user_id = u.id AND n.event_name = 'organizer.changes_requested');

INSERT INTO notifications (user_id, event_name, payload)
SELECT u.id, 'organizer.approved', '{"message": "Congratulations! Your organizer business profile has been approved at Trust Tier 2.", "tier": "TIER_2"}'::jsonb
FROM users u WHERE u.email = 'director@apex-shows.fixture.com'
AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.user_id = u.id AND n.event_name = 'organizer.approved');

