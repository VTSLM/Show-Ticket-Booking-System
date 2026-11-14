"""
Organizer Verification Test Fixtures — Sprint 2.
Person A: A-01 Deliverable.

Provides sample organizer data for:
1. Individual Organizer
2. Sole Proprietor
3. Company
4. Organizer Awaiting Verification
5. Approved Organizer
6. Organizer Whose Application Needs Changes

All data is strictly fictional and demonstrates proper masking, hashing,
and compliance with Person A contracts.
"""

from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from models.verification import (
    BusinessType,
    CaseType,
    DocumentType,
    VerificationStatus,
    ReviewStatus,
    TrustTierCode,
)
from services.verification_security import (
    mask_pan,
    mask_gstin,
    mask_bank_account,
    hash_salted_value,
)

# Deterministic fictional UUIDs for fixtures
SAMPLE_USER_IDS = {
    "individual": UUID("10000000-0000-0000-0000-000000000001"),
    "sole_proprietor": UUID("10000000-0000-0000-0000-000000000002"),
    "company": UUID("10000000-0000-0000-0000-000000000003"),
    "awaiting_verification": UUID("10000000-0000-0000-0000-000000000004"),
    "approved": UUID("10000000-0000-0000-0000-000000000005"),
    "changes_requested": UUID("10000000-0000-0000-0000-000000000006"),
}

SAMPLE_ORGANIZER_IDS = {
    "individual": UUID("20000000-0000-0000-0000-000000000001"),
    "sole_proprietor": UUID("20000000-0000-0000-0000-000000000002"),
    "company": UUID("20000000-0000-0000-0000-000000000003"),
    "awaiting_verification": UUID("20000000-0000-0000-0000-000000000004"),
    "approved": UUID("20000000-0000-0000-0000-000000000005"),
    "changes_requested": UUID("20000000-0000-0000-0000-000000000006"),
}


def get_sample_organizer_personas():
    """Returns a list of 6 fully populated sample organizer fixture dictionaries."""
    now = datetime.now(timezone.utc)

    # 1. Individual Organizer (Draft status)
    individual = {
        "id": SAMPLE_ORGANIZER_IDS["individual"],
        "user_id": SAMPLE_USER_IDS["individual"],
        "legal_name": "Rahul Sharma",
        "business_type": BusinessType.INDIVIDUAL,
        "state": "Maharashtra",
        "pan_masked": mask_pan("ABCDE1234R"),
        "gstin_masked": None,
        "verification_status": VerificationStatus.DRAFT,
        "trust_tier": TrustTierCode.TIER_1.value,
        "created_at": now,
        "updated_at": now,
        "bank_account": None,
        "documents": [],
    }

    # 2. Sole Proprietor (Approved)
    sole_prop = {
        "id": SAMPLE_ORGANIZER_IDS["sole_proprietor"],
        "user_id": SAMPLE_USER_IDS["sole_proprietor"],
        "legal_name": "Priya Patel Events",
        "business_type": BusinessType.SOLE_PROPRIETOR,
        "state": "Gujarat",
        "pan_masked": mask_pan("ABCPD5678P"),
        "gstin_masked": mask_gstin("24ABCPD5678P1Z3"),
        "verification_status": VerificationStatus.APPROVED,
        "trust_tier": TrustTierCode.TIER_1.value,
        "created_at": now,
        "updated_at": now,
        "bank_account": {
            "id": UUID("30000000-0000-0000-0000-000000000002"),
            "organizer_id": SAMPLE_ORGANIZER_IDS["sole_proprietor"],
            "holder_name": "Priya Patel",
            "ifsc": "HDFC0001234",
            "account_masked": mask_bank_account("50100234564589"),
            "account_hash": hash_salted_value("50100234564589"),
            "verified": True,
        },
        "documents": [
            {
                "id": UUID("40000000-0000-0000-0000-000000000002"),
                "case_id": SAMPLE_ORGANIZER_IDS["sole_proprietor"],
                "case_type": CaseType.ORGANIZER,
                "doc_type": DocumentType.PAN,
                "version": 1,
                "storage_ref": "vault/organizers/priya_patel/pan_v1.pdf",
                "doc_number_masked": mask_pan("ABCPD5678P"),
                "issued_by": "Income Tax Department",
                "valid_to": None,
                "review_status": ReviewStatus.APPROVED,
                "reviewer_comment": "Valid PAN card.",
                "uploaded_by": SAMPLE_USER_IDS["sole_proprietor"],
            }
        ],
    }

    # 3. Company (Large scale corporate organizer, Tier 3)
    company = {
        "id": SAMPLE_ORGANIZER_IDS["company"],
        "user_id": SAMPLE_USER_IDS["company"],
        "legal_name": "Skyline Entertainment Private Limited",
        "business_type": BusinessType.COMPANY,
        "state": "Karnataka",
        "pan_masked": mask_pan("AAACS1122C"),
        "gstin_masked": mask_gstin("29AAACS1122C2Z8"),
        "verification_status": VerificationStatus.APPROVED,
        "trust_tier": TrustTierCode.TIER_3.value,
        "created_at": now,
        "updated_at": now,
        "bank_account": {
            "id": UUID("30000000-0000-0000-0000-000000000003"),
            "organizer_id": SAMPLE_ORGANIZER_IDS["company"],
            "holder_name": "Skyline Entertainment Pvt Ltd",
            "ifsc": "ICIC0000987",
            "account_masked": mask_bank_account("00090501239012"),
            "account_hash": hash_salted_value("00090501239012"),
            "verified": True,
        },
        "documents": [
            {
                "id": UUID("40000000-0000-0000-0000-000000000003"),
                "case_id": SAMPLE_ORGANIZER_IDS["company"],
                "case_type": CaseType.ORGANIZER,
                "doc_type": DocumentType.BUSINESS_REGISTRATION,
                "version": 1,
                "storage_ref": "vault/organizers/skyline/certificate_of_inc.pdf",
                "doc_number_masked": "U74999KA2020PTC****88",
                "issued_by": "Ministry of Corporate Affairs (RoC)",
                "valid_to": None,
                "review_status": ReviewStatus.APPROVED,
                "reviewer_comment": "Verified against MCA database.",
                "uploaded_by": SAMPLE_USER_IDS["company"],
            }
        ],
    }

    # 4. Organizer Awaiting Verification (Pending)
    awaiting_verification = {
        "id": SAMPLE_ORGANIZER_IDS["awaiting_verification"],
        "user_id": SAMPLE_USER_IDS["awaiting_verification"],
        "legal_name": "Aarav Mehta Productions",
        "business_type": BusinessType.INDIVIDUAL,
        "state": "Delhi",
        "pan_masked": mask_pan("ABCPM9988M"),
        "gstin_masked": None,
        "verification_status": VerificationStatus.PENDING,
        "trust_tier": TrustTierCode.TIER_1.value,
        "created_at": now,
        "updated_at": now,
        "bank_account": {
            "id": UUID("30000000-0000-0000-0000-000000000004"),
            "organizer_id": SAMPLE_ORGANIZER_IDS["awaiting_verification"],
            "holder_name": "Aarav Mehta",
            "ifsc": "SBIN0004321",
            "account_masked": mask_bank_account("204567890123"),
            "account_hash": hash_salted_value("204567890123"),
            "verified": False,
        },
        "documents": [
            {
                "id": UUID("40000000-0000-0000-0000-000000000004"),
                "case_id": SAMPLE_ORGANIZER_IDS["awaiting_verification"],
                "case_type": CaseType.ORGANIZER,
                "doc_type": DocumentType.PAN,
                "version": 1,
                "storage_ref": "vault/organizers/aarav_mehta/pan_v1.pdf",
                "doc_number_masked": mask_pan("ABCPM9988M"),
                "issued_by": "Income Tax Department",
                "valid_to": None,
                "review_status": ReviewStatus.PENDING,
                "reviewer_comment": None,
                "uploaded_by": SAMPLE_USER_IDS["awaiting_verification"],
            }
        ],
    }

    # 5. Approved Organizer (LLP)
    approved = {
        "id": SAMPLE_ORGANIZER_IDS["approved"],
        "user_id": SAMPLE_USER_IDS["approved"],
        "legal_name": "Apex Live Events LLP",
        "business_type": BusinessType.LLP,
        "state": "Maharashtra",
        "pan_masked": mask_pan("AAACL3344L"),
        "gstin_masked": mask_gstin("27AAACL3344L1Z4"),
        "verification_status": VerificationStatus.APPROVED,
        "trust_tier": TrustTierCode.TIER_2.value,
        "created_at": now,
        "updated_at": now,
        "bank_account": {
            "id": UUID("30000000-0000-0000-0000-000000000005"),
            "organizer_id": SAMPLE_ORGANIZER_IDS["approved"],
            "holder_name": "Apex Live Events LLP",
            "ifsc": "KKBK0004567",
            "account_masked": mask_bank_account("98765432103344"),
            "account_hash": hash_salted_value("98765432103344"),
            "verified": True,
        },
        "documents": [
            {
                "id": UUID("40000000-0000-0000-0000-000000000005"),
                "case_id": SAMPLE_ORGANIZER_IDS["approved"],
                "case_type": CaseType.ORGANIZER,
                "doc_type": DocumentType.GST_CERTIFICATE,
                "version": 1,
                "storage_ref": "vault/organizers/apex_llp/gst_cert.pdf",
                "doc_number_masked": mask_gstin("27AAACL3344L1Z4"),
                "issued_by": "GSTN Council",
                "valid_to": None,
                "review_status": ReviewStatus.APPROVED,
                "reviewer_comment": "Verified active status on GST portal.",
                "uploaded_by": SAMPLE_USER_IDS["approved"],
            }
        ],
    }

    # 6. Organizer Whose Application Needs Changes (Changes Requested)
    changes_requested = {
        "id": SAMPLE_ORGANIZER_IDS["changes_requested"],
        "user_id": SAMPLE_USER_IDS["changes_requested"],
        "legal_name": "Kavita Art Foundation Trust",
        "business_type": BusinessType.TRUST,
        "state": "Rajasthan",
        "pan_masked": mask_pan("AAATK7788T"),
        "gstin_masked": None,
        "verification_status": VerificationStatus.CHANGES_REQUESTED,
        "trust_tier": TrustTierCode.TIER_1.value,
        "created_at": now,
        "updated_at": now,
        "bank_account": None,
        "documents": [
            {
                "id": UUID("40000000-0000-0000-0000-000000000006"),
                "case_id": SAMPLE_ORGANIZER_IDS["changes_requested"],
                "case_type": CaseType.ORGANIZER,
                "doc_type": DocumentType.BUSINESS_REGISTRATION,
                "version": 1,
                "storage_ref": "vault/organizers/kavita_trust/trust_deed_v1.pdf",
                "doc_number_masked": "REG-1998-****-RJ",
                "issued_by": "Charity Commissioner",
                "valid_to": None,
                "review_status": ReviewStatus.CHANGES_REQUESTED,
                "reviewer_comment": "Uploaded copy is blurry. Please provide a clear scanned copy of page 3 with trustee signatures.",
                "uploaded_by": SAMPLE_USER_IDS["changes_requested"],
            }
        ],
    }

    return [
        individual,
        sole_prop,
        company,
        awaiting_verification,
        approved,
        changes_requested,
    ]

