"""
Verification Models & Contracts — Sprint 2.
Person A: Organizer Verification Foundation & Shared Foundations (Person B Venue integration).

Defines:
- Enums: BusinessType, CaseType, DocumentType, VerificationStatus, ReviewStatus, TrustTierCode
- Pydantic Domain & Schema Contracts for:
  - TrustTierRule
  - OrganizerProfile
  - BankAccount
  - VerificationDocument (Shared with Person B)
  - DuplicateFingerprint (Shared with Person B)
  - Notification (Shared with Person B)
"""

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# ENUMS
# ==============================================================================

class BusinessType(str, Enum):
    """Allowed business entity classifications for organizers."""
    INDIVIDUAL = "INDIVIDUAL"
    SOLE_PROPRIETOR = "SOLE_PROPRIETOR"
    COMPANY = "COMPANY"
    LLP = "LLP"
    TRUST = "TRUST"


class CaseType(str, Enum):
    """Polymorphic verification case scope. Shared with Person B (Venue/Listing)."""
    ORGANIZER = "ORGANIZER"
    VENUE = "VENUE"
    LISTING = "LISTING"


class DocumentType(str, Enum):
    """
    Verification document types.
    Shared catalogue across Organizer (Person A) and Venue (Person B).
    """
    # Organizer documents (Person A)
    PAN = "PAN"
    GST_CERTIFICATE = "GST_CERTIFICATE"
    BANK_PROOF = "BANK_PROOF"
    SIGNATORY_ID = "SIGNATORY_ID"
    AUTHORISATION_LETTER = "AUTHORISATION_LETTER"
    BUSINESS_REGISTRATION = "BUSINESS_REGISTRATION"
    # Venue documents (Person B)
    CINEMA_LICENCE = "CINEMA_LICENCE"
    FIRE_NOC = "FIRE_NOC"
    ELECTRICAL_CERT = "ELECTRICAL_CERT"
    OCCUPANCY_CERT = "OCCUPANCY_CERT"
    OWNERSHIP_PROOF = "OWNERSHIP_PROOF"
    # General fallback
    OTHER = "OTHER"


class VerificationStatus(str, Enum):
    """Lifecycle status of an organizer or verification entity."""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class ReviewStatus(str, Enum):
    """Individual document review evaluation status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class TrustTierCode(str, Enum):
    """Tier identifiers defined in trust_tier_rules."""
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"


class FingerprintKind(str, Enum):
    """Category of salted fingerprint for collision / fraud detection."""
    PAN = "PAN"
    GSTIN = "GSTIN"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    PHONE = "PHONE"
    EMAIL = "EMAIL"


# ==============================================================================
# PYDANTIC CONTRACT MODELS
# ==============================================================================

class TrustTierRuleModel(BaseModel):
    """Trust tier policy and configuration schema."""
    tier: str = Field(..., max_length=50)
    max_live_shows: int = Field(default=1, ge=0)
    payout_hold_days: int = Field(default=7, ge=0)
    rules: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class OrganizerProfileCreate(BaseModel):
    """Payload for submitting or creating an organizer verification profile."""
    legal_name: str = Field(..., min_length=2, max_length=255)
    business_type: BusinessType
    state: Optional[str] = Field(None, max_length=100)
    pan_masked: Optional[str] = Field(None, max_length=20)
    gstin_masked: Optional[str] = Field(None, max_length=20)
    trust_tier: str = Field(default="TIER_1", max_length=50)

    @field_validator("legal_name")
    @classmethod
    def clean_legal_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("legal_name cannot be blank")
        return v


class OrganizerProfileModel(BaseModel):
    """Organizer profile database representation."""
    id: UUID
    user_id: UUID
    legal_name: str
    business_type: BusinessType
    state: Optional[str] = None
    pan_masked: Optional[str] = None
    gstin_masked: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    trust_tier: str = "TIER_1"
    created_at: datetime
    updated_at: datetime


class BankAccountCreate(BaseModel):
    """Payload schema for registering an organizer bank account."""
    organizer_id: UUID
    holder_name: str = Field(..., min_length=2, max_length=255)
    ifsc: str = Field(..., min_length=4, max_length=20)
    account_masked: str = Field(..., max_length=30)
    account_hash: str = Field(..., min_length=32, max_length=128)
    verified: bool = False

    @field_validator("holder_name", "ifsc", "account_masked")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class BankAccountModel(BaseModel):
    """Bank account database representation."""
    id: UUID
    organizer_id: UUID
    holder_name: str
    ifsc: str
    account_masked: str
    account_hash: str
    verified: bool = False
    created_at: datetime
    updated_at: datetime


class VerificationDocumentCreate(BaseModel):
    """Payload for registering an uploaded document for verification."""
    case_id: UUID
    case_type: CaseType
    doc_type: DocumentType
    version: int = Field(default=1, ge=1)
    storage_ref: str = Field(..., min_length=5)
    doc_number_masked: Optional[str] = Field(None, max_length=50)
    issued_by: Optional[str] = Field(None, max_length=255)
    valid_to: Optional[date] = None
    uploaded_by: Optional[UUID] = None


class VerificationDocumentModel(BaseModel):
    """Verification document database representation. Shared with Person B."""
    id: UUID
    case_id: UUID
    case_type: CaseType
    doc_type: DocumentType
    version: int = 1
    storage_ref: str
    doc_number_masked: Optional[str] = None
    issued_by: Optional[str] = None
    valid_to: Optional[date] = None
    review_status: ReviewStatus = ReviewStatus.PENDING
    reviewer_comment: Optional[str] = None
    uploaded_by: Optional[UUID] = None
    uploaded_at: datetime
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None


class DuplicateFingerprintCreate(BaseModel):
    """Registration schema for deduplication & anti-fraud fingerprints."""
    kind: str = Field(..., min_length=2, max_length=50)
    salted_hash: str = Field(..., min_length=32, max_length=128)
    case_id: UUID
    case_type: CaseType = CaseType.ORGANIZER


class DuplicateFingerprintModel(BaseModel):
    """Fingerprint database representation. Shared with Person B."""
    id: UUID
    kind: str
    salted_hash: str
    case_id: UUID
    case_type: CaseType
    created_at: datetime


class NotificationCreate(BaseModel):
    """Notification event creation schema."""
    user_id: UUID
    event_name: str = Field(..., min_length=2, max_length=100)
    payload: Dict[str, Any] = Field(default_factory=dict)
    emailed_at: Optional[datetime] = None


class NotificationModel(BaseModel):
    """Notification database representation."""
    id: UUID
    user_id: UUID
    event_name: str
    payload: Dict[str, Any]
    read_at: Optional[datetime] = None
    emailed_at: Optional[datetime] = None
    created_at: datetime

