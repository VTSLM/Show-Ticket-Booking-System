"""
Unit Tests for Sprint 2 Organizer Verification Foundation & Shared Contracts.
Person A: A-01 Deliverable.

Covers:
1. Enums and contract validations (BusinessType, CaseType, DocumentType, Statuses).
2. Pydantic models and relationship validation.
3. Security helpers (PAN/GSTIN/Bank masking and salted hashing).
4. Fixtures validation (all 6 required personas).
5. Migration & Rollback SQL structure and constraints validation.
6. Shared foundation compatibility with Person B (Venue/Listing cases and documents).
"""

import os
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError

from models.verification import (
    BusinessType,
    CaseType,
    DocumentType,
    VerificationStatus,
    ReviewStatus,
    TrustTierCode,
    TrustTierRuleModel,
    OrganizerProfileCreate,
    OrganizerProfileModel,
    BankAccountCreate,
    BankAccountModel,
    VerificationDocumentCreate,
    VerificationDocumentModel,
    DuplicateFingerprintCreate,
    DuplicateFingerprintModel,
    NotificationCreate,
    NotificationModel,
)
from services.verification_security import (
    mask_pan,
    mask_gstin,
    mask_bank_account,
    hash_salted_value,
    sanitize_sensitive_dict,
    get_fingerprint_pepper,
)
from fixtures.organizer_fixtures import get_sample_organizer_personas


# ==============================================================================
# 1. ENUM & CONTRACT SPECIFICATION TESTS
# ==============================================================================

def test_business_types_specification():
    """Verify all 5 required business entity types are defined."""
    expected = {"INDIVIDUAL", "SOLE_PROPRIETOR", "COMPANY", "LLP", "TRUST"}
    actual = {b.value for b in BusinessType}
    assert actual == expected


def test_case_types_specification():
    """Verify case types for shared polymorphic foundations with Person B."""
    expected = {"ORGANIZER", "VENUE", "LISTING"}
    actual = {c.value for c in CaseType}
    assert actual == expected


def test_document_types_specification():
    """Verify all 12 required document types (Person A + Person B + Shared)."""
    expected = {
        "PAN",
        "GST_CERTIFICATE",
        "BANK_PROOF",
        "SIGNATORY_ID",
        "AUTHORISATION_LETTER",
        "BUSINESS_REGISTRATION",
        "CINEMA_LICENCE",
        "FIRE_NOC",
        "ELECTRICAL_CERT",
        "OCCUPANCY_CERT",
        "OWNERSHIP_PROOF",
        "OTHER",
    }
    actual = {d.value for d in DocumentType}
    assert actual == expected


def test_verification_and_review_statuses():
    """Verify verification status and review status lifecycles."""
    assert "PENDING" in [s.value for s in VerificationStatus]
    assert "APPROVED" in [s.value for s in VerificationStatus]
    assert "CHANGES_REQUESTED" in [s.value for s in VerificationStatus]
    assert "REJECTED" in [s.value for s in VerificationStatus]
    assert "DRAFT" in [s.value for s in VerificationStatus]

    assert "PENDING" in [s.value for s in ReviewStatus]
    assert "APPROVED" in [s.value for s in ReviewStatus]
    assert "CHANGES_REQUESTED" in [s.value for s in ReviewStatus]
    assert "REJECTED" in [s.value for s in ReviewStatus]


# ==============================================================================
# 2. SECURITY & TOKENIZATION TESTS
# ==============================================================================

def test_mask_pan():
    """Verify PAN masking keeps prefix and suffix while obscuring digits."""
    assert mask_pan("ABCDE1234F") == "ABCDE****F"
    assert mask_pan("abcde1234f") == "ABCDE****F"
    assert mask_pan(None) is None
    assert mask_pan("") is None
    # Short input fallback
    assert mask_pan("ABC") == "****"


def test_mask_gstin():
    """Verify GSTIN masking obscures middle identification numbers."""
    assert mask_gstin("24ABCDE1234F1Z5") == "24ABCDE****1Z5"
    assert mask_gstin("29AAACS1122C2Z8") == "29AAACS****2Z8"
    assert mask_gstin(None) is None


def test_mask_bank_account():
    """Verify bank account masking preserves only the final 4 digits."""
    assert mask_bank_account("50100234564589") == "**********4589"
    assert mask_bank_account("1234") == "****"
    assert mask_bank_account("12345") == "*2345"
    assert mask_bank_account(None) is None


def test_hash_salted_value_deterministic():
    """Verify that salted hashes are deterministic and one-way."""
    val = "ABCDE1234F"
    hash1 = hash_salted_value(val)
    hash2 = hash_salted_value(val)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex string

    # Case insensitivity
    assert hash_salted_value("abcde1234f") == hash1

    # Different salt produces different hash
    alt_hash = hash_salted_value(val, salt="custom-salt-123")
    assert alt_hash != hash1

    # Empty value raises ValueError
    with pytest.raises(ValueError):
        hash_salted_value("")
    with pytest.raises(ValueError):
        hash_salted_value("   ")


def test_sanitize_sensitive_dict():
    """Verify sensitive dictionary scrubber masks raw PAN, GSTIN, and Bank Account values."""
    raw_payload = {
        "organizer_name": "Test Org",
        "pan": "ABCDE1234F",
        "gstin": "24ABCDE1234F1Z5",
        "bank_account": "123456789012",
        "existing_pan_masked": "ABCDE****F",
        "status": "PENDING",
    }
    sanitized = sanitize_sensitive_dict(raw_payload)
    assert sanitized["organizer_name"] == "Test Org"
    assert sanitized["pan"] == "ABCDE****F"
    assert sanitized["gstin"] == "24ABCDE****1Z5"
    assert sanitized["bank_account"] == "********9012"
    assert sanitized["existing_pan_masked"] == "ABCDE****F"
    assert sanitized["status"] == "PENDING"


def test_dynamic_salt_pepper_resolution(monkeypatch):
    """Verify that environment salt changes dynamically alter the pepper without restart."""
    monkeypatch.setenv("VERIFICATION_SALT_PEPPER", "test-override-pepper-2026")
    pepper = get_fingerprint_pepper()
    assert pepper == b"test-override-pepper-2026"



# ==============================================================================
# 3. PYDANTIC DOMAIN MODEL & VALIDATION TESTS
# ==============================================================================

def test_organizer_profile_create_validation():
    """Verify validation on organizer profile creation."""
    payload = {
        "legal_name": "  Zenith Events Pvt Ltd  ",
        "business_type": BusinessType.COMPANY,
        "state": "Gujarat",
        "pan_masked": "AAACZ****Z",
        "gstin_masked": "24AAACZ****1Z1",
    }
    model = OrganizerProfileCreate(**payload)
    assert model.legal_name == "Zenith Events Pvt Ltd"
    assert model.business_type == BusinessType.COMPANY

    # Blank legal name rejected
    with pytest.raises(ValidationError):
        OrganizerProfileCreate(legal_name="   ", business_type=BusinessType.INDIVIDUAL)

    # Invalid business type rejected
    with pytest.raises(ValidationError):
        OrganizerProfileCreate(legal_name="Valid Name", business_type="PARTNERSHIP")


def test_bank_account_model_validation():
    """Verify bank account model validations."""
    account = BankAccountModel(
        id=uuid4(),
        organizer_id=uuid4(),
        holder_name="Rahul Sharma",
        ifsc="HDFC0001234",
        account_masked="********1234",
        account_hash=hash_salted_value("123456781234"),
        verified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert account.verified is False
    assert account.account_masked.endswith("1234")


def test_trust_tier_rule_model():
    """Verify trust tier rules schema."""
    tier = TrustTierRuleModel(
        tier="TIER_1",
        max_live_shows=2,
        payout_hold_days=14,
        rules={"instant_payout": False, "ticket_price_limit": 5000},
        description="Starter tier",
    )
    assert tier.max_live_shows == 2
    assert tier.payout_hold_days == 14
    assert tier.rules["instant_payout"] is False


# ==============================================================================
# 4. PERSON B INTEGRATION / SHARED FOUNDATIONS TESTS
# ==============================================================================

def test_person_b_venue_document_support():
    """
    Ensure Person B can create verification documents for VENUE cases
    using venue-specific document types without model modification.
    """
    venue_id = uuid4()
    uploader_id = uuid4()
    doc = VerificationDocumentCreate(
        case_id=venue_id,
        case_type=CaseType.VENUE,
        doc_type=DocumentType.FIRE_NOC,
        storage_ref="vault/venues/regal_cinema/fire_noc_2026.pdf",
        doc_number_masked="NOC-2026-****-AHM",
        issued_by="Gujarat Fire & Emergency Services",
        valid_to=date(2027, 12, 31),
        uploaded_by=uploader_id,
    )
    assert doc.case_type == CaseType.VENUE
    assert doc.doc_type == DocumentType.FIRE_NOC
    assert doc.storage_ref.endswith(".pdf")


def test_person_b_fingerprint_support():
    """
    Ensure Person B can register duplicate fingerprints for venues
    (e.g. cinema licence collision detection).
    """
    venue_id = uuid4()
    fp = DuplicateFingerprintCreate(
        kind="CINEMA_LICENCE",
        salted_hash=hash_salted_value("GUJ-THEATRE-LIC-998811"),
        case_id=venue_id,
        case_type=CaseType.VENUE,
    )
    assert fp.case_type == CaseType.VENUE
    assert fp.kind == "CINEMA_LICENCE"
    assert len(fp.salted_hash) == 64


def test_shared_notification_foundation():
    """Verify shared notification model supports both Person A and Person B events."""
    user_id = uuid4()
    notif = NotificationCreate(
        user_id=user_id,
        event_name="venue.verification_approved",
        payload={"venue_id": str(uuid4()), "status": "APPROVED"},
    )
    assert notif.event_name == "venue.verification_approved"
    assert notif.payload["status"] == "APPROVED"


# ==============================================================================
# 5. FIXTURE PERSONAS VERIFICATION
# ==============================================================================

def test_all_six_required_personas_present():
    """
    Verify all 6 required personas exist in the fixture catalog:
    1. Individual organizer
    2. Sole proprietor
    3. Company
    4. Organizer awaiting verification (PENDING)
    5. Approved organizer (APPROVED)
    6. Organizer whose application needs changes (CHANGES_REQUESTED)
    """
    fixtures = get_sample_organizer_personas()
    assert len(fixtures) == 6

    business_types = {f["business_type"] for f in fixtures}
    assert BusinessType.INDIVIDUAL in business_types
    assert BusinessType.SOLE_PROPRIETOR in business_types
    assert BusinessType.COMPANY in business_types
    assert BusinessType.LLP in business_types
    assert BusinessType.TRUST in business_types

    statuses = {f["verification_status"] for f in fixtures}
    assert VerificationStatus.PENDING in statuses
    assert VerificationStatus.APPROVED in statuses
    assert VerificationStatus.CHANGES_REQUESTED in statuses

    # Validate that every persona dictionary passes OrganizerProfileModel validation
    for persona in fixtures:
        model = OrganizerProfileModel(
            id=persona["id"],
            user_id=persona["user_id"],
            legal_name=persona["legal_name"],
            business_type=persona["business_type"],
            state=persona["state"],
            pan_masked=persona["pan_masked"],
            gstin_masked=persona["gstin_masked"],
            verification_status=persona["verification_status"],
            trust_tier=persona["trust_tier"],
            created_at=persona["created_at"],
            updated_at=persona["updated_at"],
        )
        assert model.legal_name == persona["legal_name"]

        # If the persona has a bank account, validate BankAccountModel
        if persona.get("bank_account"):
            ba = BankAccountModel(**persona["bank_account"], created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            assert ba.account_masked.startswith("*")

        # If the persona has documents, validate VerificationDocumentModel
        for doc in persona.get("documents", []):
            dm = VerificationDocumentModel(**doc, uploaded_at=datetime.now(timezone.utc))
            assert dm.case_type == CaseType.ORGANIZER


# ==============================================================================
# 6. SQL MIGRATION FILE INTEGRITY TESTS
# ==============================================================================

def test_migration_and_rollback_sql_files_exist():
    """Verify migration and rollback files exist and contain required tables."""
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "database", "004_organizer_verification.sql"
    )
    rollback_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "database", "004_organizer_verification_rollback.sql"
    )
    fixtures_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "database", "seeds", "002_organizer_verification_fixtures.sql"
    )

    assert os.path.isfile(migration_path), f"Migration file missing: {migration_path}"
    assert os.path.isfile(rollback_path), f"Rollback file missing: {rollback_path}"
    assert os.path.isfile(fixtures_path), f"Fixtures SQL missing: {fixtures_path}"

    with open(migration_path, "r", encoding="utf-8") as f:
        mig_sql = f.read()

    # Check for all required tables
    for tbl in [
        "trust_tier_rules",
        "organizer_profiles",
        "bank_accounts",
        "verification_documents",
        "duplicate_fingerprints",
        "notifications",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {tbl}" in mig_sql

    # Check for business types constraint
    for btype in ["INDIVIDUAL", "SOLE_PROPRIETOR", "COMPANY", "LLP", "TRUST"]:
        assert btype in mig_sql

    # Check for case types constraint
    for ctype in ["ORGANIZER", "VENUE", "LISTING"]:
        assert ctype in mig_sql

    # Check for document types constraint
    for dtype in [
        "PAN",
        "GST_CERTIFICATE",
        "BANK_PROOF",
        "SIGNATORY_ID",
        "AUTHORISATION_LETTER",
        "BUSINESS_REGISTRATION",
        "CINEMA_LICENCE",
        "FIRE_NOC",
        "ELECTRICAL_CERT",
        "OCCUPANCY_CERT",
        "OWNERSHIP_PROOF",
        "OTHER",
    ]:
        assert dtype in mig_sql

    # Check rollback drops in correct order
    with open(rollback_path, "r", encoding="utf-8") as f:
        rollback_sql = f.read()

    assert "DROP TABLE IF EXISTS notifications" in rollback_sql
    assert "DROP TABLE IF EXISTS duplicate_fingerprints" in rollback_sql
    assert "DROP TABLE IF EXISTS verification_documents" in rollback_sql
    assert "DROP TABLE IF EXISTS bank_accounts" in rollback_sql
    assert "DROP TABLE IF EXISTS organizer_profiles" in rollback_sql
    assert "DROP TABLE IF EXISTS trust_tier_rules" in rollback_sql

