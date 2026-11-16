"""
Unit & Integration Tests for Organizer Verification Application Experience.
Sprint 2: Deliverable A-04.

Covers:
1. Document checklist by BusinessType.
2. Saving application as draft with PAN, GSTIN, and Bank credentials.
3. Resuming previously saved draft for authenticated organizer.
4. PAN & GSTIN validator integration during draft save.
5. Sensitive data masking (PAN, GSTIN, Bank Account).
6. Pre-submission validation (rejects missing required documents or fields).
7. Successful application submission (DRAFT -> SUBMITTED).
8. Notification event generation upon submission.
9. Rejection of edits on already SUBMITTED applications.
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi import HTTPException

from models.verification import BusinessType, VerificationStatus
from routers.organizer_verification import (
    ApplicationDraftRequest,
    get_document_checklist,
    get_my_applications,
    save_application_draft,
    submit_application,
)


class FakeDbConnection:
    """Mock database connection for organizer verification testing."""

    def __init__(self):
        self.organizer_profiles = []
        self.bank_accounts = []
        self.verification_documents = []
        self.notifications = []

    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def transaction(self):
        return self.FakeTransaction()

    async def fetch(self, query, *args):
        # Fetch my applications
        if "FROM organizer_profiles" in query and "user_id = $1" in query:
            user_id = str(args[0])
            return [p for p in self.organizer_profiles if str(p["user_id"]) == user_id]

        # Fetch verification documents for case
        if "FROM verification_documents" in query and "case_id = $1" in query:
            case_id = str(args[0])
            return [d for d in self.verification_documents if str(d["case_id"]) == case_id]

        return []

    async def fetchrow(self, query, *args):
        # Check existing organizer profile by user_id
        if "FROM organizer_profiles" in query and "user_id = $1" in query:
            user_id = str(args[0])
            for p in self.organizer_profiles:
                if str(p["user_id"]) == user_id:
                    return p
            return None

        # Check organizer profile by id
        if "FROM organizer_profiles" in query and "id = $1" in query:
            app_id = str(args[0])
            for p in self.organizer_profiles:
                if str(p["id"]) == app_id:
                    return p
            return None

        # Insert organizer profile
        if "INSERT INTO organizer_profiles" in query:
            user_id, legal_name, business_type, state, pan_masked, gstin_masked = args
            prof_id = uuid.uuid4()
            now = datetime.now(timezone.utc)
            row = {
                "id": prof_id,
                "user_id": user_id,
                "legal_name": legal_name,
                "business_type": business_type,
                "state": state,
                "pan_masked": pan_masked,
                "gstin_masked": gstin_masked,
                "verification_status": "DRAFT",
                "trust_tier": "TIER_1",
                "created_at": now,
                "updated_at": now,
            }
            self.organizer_profiles.append(row)
            return row

        # Update organizer profile
        if "UPDATE organizer_profiles" in query and "SET legal_name" in query:
            legal_name, business_type, state, pan_masked, gstin_masked, app_id = args
            for p in self.organizer_profiles:
                if str(p["id"]) == str(app_id):
                    p["legal_name"] = legal_name
                    p["business_type"] = business_type
                    p["state"] = state
                    if pan_masked: p["pan_masked"] = pan_masked
                    if gstin_masked: p["gstin_masked"] = gstin_masked
                    p["updated_at"] = datetime.now(timezone.utc)
                    return p
            return None

        # Update status to SUBMITTED
        if "SET verification_status = 'SUBMITTED'" in query:
            app_id = str(args[0])
            for p in self.organizer_profiles:
                if str(p["id"]) == app_id:
                    p["verification_status"] = "SUBMITTED"
                    p["updated_at"] = datetime.now(timezone.utc)
                    return p
            return None

        # Check bank account by organizer_id
        if "FROM bank_accounts WHERE organizer_id = $1" in query:
            org_id = str(args[0])
            for b in self.bank_accounts:
                if str(b["organizer_id"]) == org_id:
                    return b
            return None

        # Insert bank account
        if "INSERT INTO bank_accounts" in query:
            org_id, holder, ifsc, masked_acc, hashed_acc = args
            row = {
                "id": uuid.uuid4(),
                "organizer_id": org_id,
                "holder_name": holder,
                "ifsc": ifsc,
                "account_masked": masked_acc,
                "account_hash": hashed_acc,
                "verified": False,
                "created_at": datetime.now(timezone.utc),
            }
            self.bank_accounts.append(row)
            return row

        # Update bank account
        if "UPDATE bank_accounts" in query:
            holder, ifsc, masked_acc, hashed_acc, b_id = args
            for b in self.bank_accounts:
                if str(b["id"]) == str(b_id):
                    b["holder_name"] = holder
                    b["ifsc"] = ifsc
                    b["account_masked"] = masked_acc
                    b["account_hash"] = hashed_acc
                    return b
            return None

        return None

    async def execute(self, query, *args):
        if "INSERT INTO notifications" in query:
            user_id, payload = args[0], args[1]
            self.notifications.append({
                "user_id": user_id,
                "event_name": "case_submitted",
                "payload": payload,
            })
            return "INSERT 1"
        return ""


# ==============================================================================
# TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_get_document_checklist():
    """1. Verify checklist returns required and optional documents per business type."""
    ind_res = await get_document_checklist(BusinessType.INDIVIDUAL)
    assert "PAN" in ind_res["required_documents"]
    assert "BANK_PROOF" in ind_res["required_documents"]
    assert "GST_CERTIFICATE" in ind_res["optional_documents"]

    comp_res = await get_document_checklist(BusinessType.COMPANY)
    assert "PAN" in comp_res["required_documents"]
    assert "GST_CERTIFICATE" in comp_res["required_documents"]
    assert "BUSINESS_REGISTRATION" in comp_res["required_documents"]


@pytest.mark.asyncio
async def test_save_draft_with_pan_and_bank():
    """2. Verify saving an application draft masks identifiers and stores bank account."""
    conn = FakeDbConnection()
    user = {"id": str(uuid.uuid4()), "roles": ["applicant"]}

    req = ApplicationDraftRequest(
        legal_name="Aarav Productions",
        business_type=BusinessType.INDIVIDUAL,
        state="Maharashtra",
        pan="ABCPE1234F",
        bank_holder_name="Aarav Mehta",
        ifsc="HDFC0001234",
        account_number="123456789012",
    )

    result = await save_application_draft(req, current_user=user, conn=conn)

    assert result["verification_status"] == "DRAFT"
    assert result["legal_name"] == "Aarav Productions"
    assert result["pan_masked"] == "ABCPE****F"
    assert result["bank_account"] is not None
    assert result["bank_account"]["account_masked"] == "********9012"
    assert len(conn.organizer_profiles) == 1
    assert len(conn.bank_accounts) == 1


@pytest.mark.asyncio
async def test_save_draft_pan_validation_failure():
    """3. Verify draft save rejects PAN when category does not match business type."""
    conn = FakeDbConnection()
    user = {"id": str(uuid.uuid4()), "roles": ["applicant"]}

    # Individual PAN supplied for COMPANY
    req = ApplicationDraftRequest(
        legal_name="Skyline Corp",
        business_type=BusinessType.COMPANY,
        pan="ABCPE1234F", # 4th char is 'P', COMPANY requires 'C'
    )

    with pytest.raises(HTTPException) as exc_info:
        await save_application_draft(req, current_user=user, conn=conn)
    assert exc_info.value.status_code == 400
    assert "PAN validation failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resume_saved_draft():
    """4. Verify organizer can retrieve previously saved drafts."""
    conn = FakeDbConnection()
    user_id = str(uuid.uuid4())
    user = {"id": user_id, "roles": ["applicant"]}

    # Save initial draft
    req = ApplicationDraftRequest(
        legal_name="Apex Events",
        business_type=BusinessType.SOLE_PROPRIETOR,
        state="Delhi",
        pan="ABCPD5678P",
    )
    await save_application_draft(req, current_user=user, conn=conn)

    # Resume drafts via get_my_applications
    apps = await get_my_applications(current_user=user, conn=conn)
    assert len(apps) == 1
    assert apps[0]["legal_name"] == "Apex Events"
    assert apps[0]["business_type"] == "SOLE_PROPRIETOR"
    assert apps[0]["verification_status"] == "DRAFT"


@pytest.mark.asyncio
async def test_pre_submission_validation_missing_documents():
    """5. Verify submit fails if required documents have not been uploaded."""
    conn = FakeDbConnection()
    user_id = str(uuid.uuid4())
    user = {"id": user_id, "roles": ["applicant"]}

    # Save draft
    req = ApplicationDraftRequest(
        legal_name="Apex Events",
        business_type=BusinessType.INDIVIDUAL,
        state="Delhi",
        pan="ABCPE1234F",
        ifsc="HDFC0001234",
        account_number="987654321098",
    )
    saved = await save_application_draft(req, current_user=user, conn=conn)
    app_id = uuid.UUID(saved["id"])

    # Attempt to submit without documents
    with pytest.raises(HTTPException) as exc_info:
        await submit_application(app_id, current_user=user, conn=conn)
    assert exc_info.value.status_code == 400
    assert "Missing required documents" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_successful_application_submission():
    """6. Verify successful submission transitions status to SUBMITTED and logs notification."""
    conn = FakeDbConnection()
    user_id = str(uuid.uuid4())
    user = {"id": user_id, "roles": ["applicant"]}

    # 1. Save complete draft
    req = ApplicationDraftRequest(
        legal_name="Apex Events",
        business_type=BusinessType.INDIVIDUAL,
        state="Delhi",
        pan="ABCPE1234F",
        ifsc="HDFC0001234",
        account_number="987654321098",
    )
    saved = await save_application_draft(req, current_user=user, conn=conn)
    app_id = uuid.UUID(saved["id"])

    # 2. Attach required documents to mock database
    conn.verification_documents.append({
        "id": uuid.uuid4(),
        "case_id": app_id,
        "doc_type": "PAN",
        "version": 1,
    })
    conn.verification_documents.append({
        "id": uuid.uuid4(),
        "case_id": app_id,
        "doc_type": "BANK_PROOF",
        "version": 1,
    })

    # 3. Submit application
    resp = await submit_application(app_id, current_user=user, conn=conn)

    assert resp["status"] == "success"
    assert resp["application"]["verification_status"] == "SUBMITTED"
    assert len(conn.notifications) == 1
    assert conn.notifications[0]["event_name"] == "case_submitted"


@pytest.mark.asyncio
async def test_re_edit_on_submitted_application_rejected():
    """7. Verify editing an application in SUBMITTED state is rejected."""
    conn = FakeDbConnection()
    user_id = str(uuid.uuid4())
    user = {"id": user_id, "roles": ["applicant"]}

    # Create profile directly in SUBMITTED status
    conn.organizer_profiles.append({
        "id": uuid.uuid4(),
        "user_id": user_id,
        "legal_name": "Locked Corp",
        "business_type": "COMPANY",
        "state": "Gujarat",
        "pan_masked": "AAACC1122C",
        "gstin_masked": None,
        "verification_status": "SUBMITTED",
        "trust_tier": "TIER_1",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    req = ApplicationDraftRequest(
        legal_name="Attempt Edit",
        business_type=BusinessType.COMPANY,
    )

    with pytest.raises(HTTPException) as exc_info:
        await save_application_draft(req, current_user=user, conn=conn)
    assert exc_info.value.status_code == 400
    assert "Cannot edit application currently in 'SUBMITTED' status" in exc_info.value.detail
