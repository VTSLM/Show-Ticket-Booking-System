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
from services.bank_verification import verify_mock_bank_account
from services.duplicate_detection import check_duplicate_collisions, register_case_fingerprints
from services.identity_validators import validate_pan, validate_gstin, validate_ifsc
from services.trust_tier_service import evaluate_payout_eligibility
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
    application_id: Optional[str] = None
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


@router.get("/applications/me", summary="Get all organizer verification applications for current user")
async def get_my_applications(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Fetch all organizer verification applications/drafts owned by the authenticated user.
    Includes masked bank accounts and attached document version history.
    """
    user_id = current_user["id"]

    profiles = await conn.fetch(
        """
        SELECT id, user_id, legal_name, business_type, state, pan_masked,
               gstin_masked, verification_status, trust_tier, created_at, updated_at
        FROM organizer_profiles
        WHERE user_id = $1
        ORDER BY updated_at DESC
        """,
        user_id,
    )

    results = []
    for p in profiles:
        prof_dict = dict(p)
        prof_id = prof_dict["id"]

        # Fetch bank account
        bank_row = await conn.fetchrow(
            """
            SELECT id, holder_name, ifsc, account_masked, verified, created_at
            FROM bank_accounts
            WHERE organizer_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            prof_id,
        )
        prof_dict["bank_account"] = dict(bank_row) if bank_row else None
        if prof_dict["bank_account"]:
            prof_dict["bank_account"]["id"] = str(prof_dict["bank_account"]["id"])
            if prof_dict["bank_account"].get("created_at"):
                prof_dict["bank_account"]["created_at"] = prof_dict["bank_account"]["created_at"].isoformat()

        # Fetch attached verification documents
        doc_rows = await conn.fetch(
            """
            SELECT id, case_id, case_type, doc_type, version, doc_number_masked,
                   issued_by, valid_to, review_status, reviewer_comment, uploaded_at
            FROM verification_documents
            WHERE case_id = $1
            ORDER BY doc_type, version DESC
            """,
            prof_id,
        )
        docs = []
        for d in doc_rows:
            doc_dict = dict(d)
            doc_dict["id"] = str(doc_dict["id"])
            doc_dict["case_id"] = str(doc_dict["case_id"])
            if doc_dict.get("valid_to"):
                doc_dict["valid_to"] = doc_dict["valid_to"].isoformat()
            if doc_dict.get("uploaded_at"):
                doc_dict["uploaded_at"] = doc_dict["uploaded_at"].isoformat()
            docs.append(doc_dict)

        prof_dict["documents"] = docs
        prof_dict["id"] = str(prof_dict["id"])
        prof_dict["user_id"] = str(prof_dict["user_id"])
        prof_dict["created_at"] = prof_dict["created_at"].isoformat()
        prof_dict["updated_at"] = prof_dict["updated_at"].isoformat()
        results.append(prof_dict)

    return results


@router.post("/applications", status_code=status.HTTP_200_OK, summary="Save or update an organizer application draft")
async def save_application_draft(
    payload: ApplicationDraftRequest,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Create or update an organizer application draft.
    Validates provided credentials format and masks sensitive data before saving.
    """
    user_id = current_user["id"]

    # 1. Validate PAN format if provided
    pan_masked = None
    if payload.pan and payload.pan.strip():
        pan_res = validate_pan(payload.pan, business_type=payload.business_type)
        if not pan_res.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"PAN validation failed: {pan_res.error_message}",
            )
        pan_masked = mask_pan(payload.pan)

    # 2. Validate GSTIN format if provided
    gstin_masked = None
    if payload.gstin and payload.gstin.strip():
        gstin_res = validate_gstin(payload.gstin, expected_pan=payload.pan)
        if not gstin_res.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GSTIN validation failed: {gstin_res.error_message}",
            )
        gstin_masked = mask_gstin(payload.gstin)

    # 3. Validate Bank IFSC if provided
    if payload.ifsc and payload.ifsc.strip():
        ifsc_res = validate_ifsc(payload.ifsc)
        if not ifsc_res.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"IFSC validation failed: {ifsc_res.error_message}",
            )

    async with conn.transaction():
        # Check if an existing profile exists for this organization application
        if payload.application_id:
            existing_profile = await conn.fetchrow(
                "SELECT id, verification_status FROM organizer_profiles WHERE id = $1 AND user_id = $2",
                payload.application_id,
                user_id,
            )
        else:
            existing_profile = await conn.fetchrow(
                "SELECT id, verification_status FROM organizer_profiles WHERE user_id = $1 AND legal_name = $2",
                user_id,
                payload.legal_name.strip(),
            )

        if existing_profile:
            current_status = existing_profile["verification_status"]
            if current_status not in ("DRAFT", "CHANGES_REQUESTED", "PENDING"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot edit application currently in '{current_status}' status.",
                )

            # Update existing profile
            profile_row = await conn.fetchrow(
                """
                UPDATE organizer_profiles
                SET legal_name = $1,
                    business_type = $2,
                    state = $3,
                    pan_masked = COALESCE($4, pan_masked),
                    gstin_masked = COALESCE($5, gstin_masked),
                    updated_at = now()
                WHERE id = $6
                RETURNING id, user_id, legal_name, business_type, state, pan_masked,
                          gstin_masked, verification_status, trust_tier, created_at, updated_at
                """,
                payload.legal_name.strip(),
                payload.business_type.value,
                payload.state.strip() if payload.state else None,
                pan_masked,
                gstin_masked,
                existing_profile["id"],
            )
            organizer_id = existing_profile["id"]
        else:
            # Create new draft profile
            profile_row = await conn.fetchrow(
                """
                INSERT INTO organizer_profiles (
                    user_id, legal_name, business_type, state, pan_masked,
                    gstin_masked, verification_status, trust_tier
                )
                VALUES ($1, $2, $3, $4, $5, $6, 'DRAFT', 'TIER_1')
                RETURNING id, user_id, legal_name, business_type, state, pan_masked,
                          gstin_masked, verification_status, trust_tier, created_at, updated_at
                """,
                user_id,
                payload.legal_name.strip(),
                payload.business_type.value,
                payload.state.strip() if payload.state else None,
                pan_masked,
                gstin_masked,
            )
            organizer_id = profile_row["id"]

        # 4. Upsert Bank Account if provided
        bank_data = None
        if payload.account_number and payload.account_number.strip() and payload.ifsc:
            masked_acc = mask_bank_account(payload.account_number)
            hashed_acc = hash_salted_value(payload.account_number, salt="tf_bank_salt")
            holder = (payload.bank_holder_name or payload.legal_name).strip()
            clean_ifsc = payload.ifsc.strip().upper()

            # Check if bank account exists for this organizer
            existing_bank = await conn.fetchrow(
                "SELECT id FROM bank_accounts WHERE organizer_id = $1",
                organizer_id,
            )
            if existing_bank:
                b_row = await conn.fetchrow(
                    """
                    UPDATE bank_accounts
                    SET holder_name = $1,
                        ifsc = $2,
                        account_masked = $3,
                        account_hash = $4,
                        updated_at = now()
                    WHERE id = $5
                    RETURNING id, holder_name, ifsc, account_masked, verified, created_at
                    """,
                    holder,
                    clean_ifsc,
                    masked_acc,
                    hashed_acc,
                    existing_bank["id"],
                )
            else:
                b_row = await conn.fetchrow(
                    """
                    INSERT INTO bank_accounts (
                        organizer_id, holder_name, ifsc, account_masked, account_hash
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id, holder_name, ifsc, account_masked, verified, created_at
                    """,
                    organizer_id,
                    holder,
                    clean_ifsc,
                    masked_acc,
                    hashed_acc,
                )
            bank_data = dict(b_row)
            bank_data["id"] = str(bank_data["id"])

    response_dict = dict(profile_row)
    response_dict["id"] = str(response_dict["id"])
    response_dict["user_id"] = str(response_dict["user_id"])
    response_dict["created_at"] = response_dict["created_at"].isoformat()
    response_dict["updated_at"] = response_dict["updated_at"].isoformat()
    response_dict["bank_account"] = bank_data

    return response_dict


@router.post("/applications/{application_id}/submit", summary="Submit an organizer application for admin review")
async def submit_application(
    application_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Validate all required fields and documents, then submit the application.
    Transitions status from DRAFT or CHANGES_REQUESTED to SUBMITTED.
    """
    user_id = current_user["id"]

    profile_row = await conn.fetchrow(
        """
        SELECT id, user_id, legal_name, business_type, state, pan_masked,
               gstin_masked, verification_status, trust_tier
        FROM organizer_profiles
        WHERE id = $1
        """,
        application_id,
    )
    if not profile_row:
        raise HTTPException(status_code=404, detail="Organizer application not found")

    if str(profile_row["user_id"]) != str(user_id) and "admin" not in current_user.get("roles", []):
        raise HTTPException(status_code=403, detail="You do not have permission to submit this application")

    curr_status = profile_row["verification_status"]
    if curr_status not in ("DRAFT", "CHANGES_REQUESTED", "PENDING"):
        raise HTTPException(
            status_code=400,
            detail=f"Application cannot be submitted because it is currently '{curr_status}'.",
        )

    # Pre-submission checks
    errors = []
    if not profile_row["legal_name"]:
        errors.append("Legal name is required.")
    if not profile_row["business_type"]:
        errors.append("Business type is required.")
    if not profile_row["state"]:
        errors.append("State is required.")
    if not profile_row["pan_masked"]:
        errors.append("A valid PAN is required.")

    b_type = BusinessType(profile_row["business_type"])
    if b_type in (BusinessType.COMPANY, BusinessType.LLP) and not profile_row["gstin_masked"]:
        errors.append("GSTIN is required for Company and LLP entities.")

    # Check bank account exists
    bank_row = await conn.fetchrow(
        "SELECT id, holder_name, ifsc, account_masked FROM bank_accounts WHERE organizer_id = $1",
        application_id,
    )
    if not bank_row:
        errors.append("Bank account details must be completed.")

    # Check required documents
    required_docs = REQUIRED_DOCUMENTS_BY_TYPE.get(b_type, [DocumentType.PAN, DocumentType.BANK_PROOF])
    uploaded_docs = await conn.fetch(
        "SELECT DISTINCT doc_type FROM verification_documents WHERE case_id = $1",
        application_id,
    )
    uploaded_doc_types = {d["doc_type"] for d in uploaded_docs}

    missing_docs = [r.value for r in required_docs if r.value not in uploaded_doc_types]
    if missing_docs:
        errors.append(f"Missing required documents: {', '.join(missing_docs)}")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Pre-submission validation failed", "errors": errors},
        )

    # Transition to SUBMITTED, execute verification adapters, and log notification
    async with conn.transaction():
        updated_row = await conn.fetchrow(
            """
            UPDATE organizer_profiles
            SET verification_status = 'SUBMITTED',
                reviewer_id = NULL,
                claimed_at = NULL,
                claim_expires_at = NULL,
                updated_at = now()
            WHERE id = $1
            RETURNING id, user_id, legal_name, business_type, state, pan_masked,
                      gstin_masked, verification_status, trust_tier, created_at, updated_at
            """,
            application_id,
        )

        # 1. Register fingerprints for collision prevention
        await register_case_fingerprints(
            conn=conn,
            case_id=application_id,
            case_type=CaseType.ORGANIZER,
            pan=profile_row["pan_masked"],
            gstin=profile_row["gstin_masked"],
            bank_account=bank_row["account_masked"] if bank_row else None,
        )

        # 2. Execute mock bank verification adapter
        if bank_row:
            bank_val = verify_mock_bank_account(
                holder_name=bank_row["holder_name"],
                ifsc=bank_row["ifsc"],
                account_number=bank_row["account_masked"],
            )
            if bank_val.get("verified"):
                await conn.execute(
                    "UPDATE bank_accounts SET verified = true, updated_at = now() WHERE id = $1",
                    bank_row["id"],
                )

        # 3. Emit notification event
        notification_payload = json.dumps({
            "case_id": str(application_id),
            "status": "SUBMITTED",
            "legal_name": profile_row["legal_name"],
        })
        await conn.execute(
            """
            INSERT INTO notifications (user_id, event_name, payload)
            VALUES ($1, 'case_submitted', $2::jsonb)
            """,
            user_id,
            notification_payload,
        )

    resp = dict(updated_row)
    resp["id"] = str(resp["id"])
    resp["user_id"] = str(resp["user_id"])
    resp["created_at"] = resp["created_at"].isoformat()
    resp["updated_at"] = resp["updated_at"].isoformat()

    return {
        "status": "success",
        "message": "Application submitted successfully for verification review.",
        "application": resp,
    }


@router.get("/payout-eligibility", summary="Get payout settlement eligibility for current organizer")
async def get_my_payout_eligibility(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Evaluate authenticated organizer's payout eligibility."""
    user_id = current_user["id"]
    prof = await conn.fetchrow(
        "SELECT id FROM organizer_profiles WHERE user_id = $1",
        user_id,
    )
    if not prof:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organizer profile found for current user. Please submit an application first.",
        )
    return await evaluate_payout_eligibility(conn=conn, organizer_id=prof["id"])
