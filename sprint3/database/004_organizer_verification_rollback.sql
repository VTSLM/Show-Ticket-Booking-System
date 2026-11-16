-- ==============================================================================
-- TicketFlow — Sprint 2: Organizer Verification & Shared Admin Foundations
-- Rollback: 004_organizer_verification_rollback.sql
--
-- Safely rolls back tables created in 004_organizer_verification.sql in reverse order.
-- ==============================================================================

DROP TRIGGER IF EXISTS trg_bank_accounts_updated_at ON bank_accounts;
DROP TRIGGER IF EXISTS trg_organizer_profiles_updated_at ON organizer_profiles;
DROP TRIGGER IF EXISTS trg_trust_tier_rules_updated_at ON trust_tier_rules;

DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS duplicate_fingerprints CASCADE;
DROP TABLE IF EXISTS verification_documents CASCADE;
DROP TABLE IF EXISTS bank_accounts CASCADE;
DROP TABLE IF EXISTS organizer_profiles CASCADE;
DROP TABLE IF EXISTS trust_tier_rules CASCADE;

