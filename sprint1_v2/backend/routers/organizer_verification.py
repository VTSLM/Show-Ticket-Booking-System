"""
Organizer Verification Application Router — Sprint 2.
Person A: Deliverable A-04 (Organizer Application Experience).

Core Responsibilities:
1. Save application as draft (supports progressive multi-step drafts).
2. Resume previously saved drafts for the authenticated organizer.
3. Validate business identity using A-02 validators (PAN, GSTIN, IFSC).
4. Mask and tokenize sensitive identifiers using A-01 security utilities.
5. Provide required document checklist based on BusinessType.
6. Enforce pre-submission validation (required fields + required documents).
7. Handle application submission (DRAFT / CHANGES_REQUESTED -> SUBMITTED).
8. Record audit notifications upon submission.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user
from models.verification import BusinessType, CaseType, DocumentType, VerificationStatus
from services.identity_validators import validate_pan, validate_gstin, validate_ifsc
from services.verification_security import (
    mask_pan,
    mask_gstin,
    mask_bank_account,
    hash_salted_value,
)

router = APIRouter(prefix="/api/verification/organizer", tags=["Organizer Verification"])

# Required documents checklist by BusinessType
REQUIRED_DOCUMENTS_BY_TYPE: Dict[BusinessType, List[DocumentType]] = {
    BusinessType.INDIVIDUAL: [
        DocumentType.PAN,
        DocumentType.BANK_PROOF,
    ],
    BusinessType.SOLE_PROPRIETOR: [
        DocumentType.PAN,
        DocumentType.BANK_PROOF,
    ],
    BusinessType.COMPANY: [
        DocumentType.PAN,
        DocumentType.GST_CERTIFICATE,
        DocumentType.BANK_PROOF,
        DocumentType.BUSINESS_REGISTRATION,
    ],
    BusinessType.LLP: [
        DocumentType.PAN,
        DocumentType.GST_CERTIFICATE,
        DocumentType.BANK_PROOF,
        DocumentType.BUSINESS_REGISTRATION,
    ],
    BusinessType.TRUST: [
        DocumentType.PAN,
        DocumentType.BANK_PROOF,
        DocumentType.BUSINESS_REGISTRATION,
    ],
}


class ApplicationDraftRequest(BaseModel):
    legal_name: str = Field(..., min_length=2, max_length=255)
    business_type: BusinessType
    state: Optional[str] = Field(None, max_length=100)
    pan: Optional[str] = None
    gstin: Optional[str] = None
    bank_holder_name: Optional[str] = None
    ifsc: Optional[str] = None
    account_number: Optional[str] = None


@router.get("/checklist", summary="Get required document types for a business type")
async def get_document_checklist(business_type: BusinessType):
    """Returns required and optional document types for the specified business type."""
    required = REQUIRED_DOCUMENTS_BY_TYPE.get(business_type, [DocumentType.PAN, DocumentType.BANK_PROOF])
    all_types = [d.value for d in DocumentType]
    optional = [d for d in all_types if d not in [r.value for r in required]]
    return {
        "business_type": business_type.value,
        "required_documents": [r.value for r in required],
        "optional_documents": optional,
    }
