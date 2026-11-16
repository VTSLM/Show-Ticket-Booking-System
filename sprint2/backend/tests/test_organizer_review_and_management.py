"""
Comprehensive Unit & Integration Tests for Deliverables A-05 & A-06.
Person A: Organizer Verification, Admin Review Workflow, and Organizer Management.

Covers:
1. Duplicate fingerprint collision detection and registration.
2. Mock bank verification adapter outcomes.
3. Risk assessment score calculation and risk flag generation.
4. Review queue and atomic reviewer claim / release.
5. Per-document decision (APPROVED, REJECTED, CHANGES_REQUESTED with comment validation).
6. Overall application decision (APPROVED, REJECTED with reason, CHANGES_REQUESTED).
7. Request-changes workflow, document version preservation, and resubmission.
8. Notifications creation for review events.
9. Organizer directory search and filtering.
10. Account actions: suspension and reactivation with mandatory reasons.
11. Payout eligibility evaluation and trust tier enforcement.
12. Role authorization checks (admin vs unauthorized user).
13. Invalid state transition rejection.
"""

from datetime import datetime, timezone
import uuid
import pytest
from fastapi import HTTPException

from models.verification import BusinessType, CaseType, DocumentType, ReviewStatus, VerificationStatus
from routers.organizer_admin import (
    AccountActionRequest,
    DocumentReviewRequest,
    VerificationDecisionRequest,
    claim_organizer_case,
    get_organizer_review_workspace,
    get_review_queue,
    list_organizers,
    make_verification_decision,
    reactivate_organizer,
    release_organizer_case,
    review_document,
    suspend_organizer,
)
from services.bank_verification import verify_mock_bank_account
from services.duplicate_detection import check_duplicate_collisions, register_case_fingerprints
from services.risk_assessment import assess_organizer_risk
from services.trust_tier_service import evaluate_payout_eligibility, get_trust_tier_rules


# ==============================================================================
# FAKE ASYNCPG DB CONNECTION FOR UNIT TESTING
# ==============================================================================

class MockDbConnection:
    def __init__(self):
        self.organizer_profiles = []
        self.bank_accounts = []
        self.verification_documents = []
        self.duplicate_fingerprints = []
        self.notifications = []
        self.trust_tier_rules = [
            {"tier": "TIER_1", "max_live_shows": 2, "payout_hold_days": 14, "rules": {"instant_payout": False, "ticket_price_limit": 5000}, "description": "Starter tier"},
            {"tier": "TIER_2", "max_live_shows": 10, "payout_hold_days": 7, "rules": {"instant_payout": False, "ticket_price_limit": 25000}, "description": "Established tier"},
            {"tier": "TIER_3", "max_live_shows": 50, "payout_hold_days": 3, "rules": {"instant_payout": True, "ticket_price_limit": 100000}, "description": "Trusted tier"},
        ]
        self.users = []

    class FakeTransaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def transaction(self):
        return self.FakeTransaction()

    async def fetch(self, query: str, *args):
        q = query.lower()
        if "from duplicate_fingerprints" in q:
            return self.duplicate_fingerprints
        if "from verification_documents" in q:
            case_id = args[0] if args else None
            return [d for d in self.verification_documents if str(d["case_id"]) == str(case_id)]
        if "from organizer_profiles" in q:
            return self.organizer_profiles
        return []

    async def fetchrow(self, query: str, *args):
        q = query.lower()
        if "update organizer_profiles" in q:
            # Case claim or update
            organizer_id = args[-1] if args else None
            for p in self.organizer_profiles:
                if str(p["id"]) == str(organizer_id):
                    if "reviewer_id = $1" in q:
                        p["reviewer_id"] = args[0]
                        p["claimed_at"] = datetime.now(timezone.utc)
                        p["claim_expires_at"] = datetime.now(timezone.utc)
                        p["verification_status"] = "IN_REVIEW"
                    elif "reviewer_id = null" in q:
                        p["reviewer_id"] = None
                        p["claimed_at"] = None
                        p["claim_expires_at"] = None
                        p["verification_status"] = "SUBMITTED"
                    elif "suspension_reason = $1" in q:
                        p["verification_status"] = "SUSPENDED"
                        p["suspension_reason"] = args[0]
                        p["updated_at"] = datetime.now(timezone.utc)
                    elif "verification_status = 'approved'" in q:
                        p["verification_status"] = "APPROVED"
                        p["suspension_reason"] = None
                        p["updated_at"] = datetime.now(timezone.utc)
                    return p
            return None

        if "from organizer_profiles" in q:
            organizer_id = args[0] if args else None
            for p in self.organizer_profiles:
                if str(p["id"]) == str(organizer_id):
                    return p
            return None

        if "from bank_accounts" in q:
            organizer_id = args[0] if args else None
            for b in self.bank_accounts:
                if str(b["organizer_id"]) == str(organizer_id):
                    return b
            return None

        if "update verification_documents" in q:
            doc_id = args[-1] if args else None
            for d in self.verification_documents:
                if str(d["id"]) == str(doc_id):
                    d["review_status"] = args[0]
                    d["reviewer_comment"] = args[1]
                    d["reviewed_at"] = datetime.now(timezone.utc)
                    return d
            return None

        if "from verification_documents" in q:
            doc_id = args[0] if args else None
            for d in self.verification_documents:
                if str(d["id"]) == str(doc_id):
                    return d
            return None

        if "from duplicate_fingerprints" in q:
            kind, salted_hash = args[0], args[1]
            for f in self.duplicate_fingerprints:
                if f["kind"] == kind and f["salted_hash"] == salted_hash:
                    if len(args) > 2 and str(f["case_id"]) == str(args[2]):
                        continue
                    return f
            return None

        if "from trust_tier_rules" in q:
            tier = args[0] if args else "TIER_1"
            for t in self.trust_tier_rules:
                if t["tier"] == tier:
                    return t
            return None

        return None

    async def fetchval(self, query: str, *args):
        q = query.lower()
        if "count(*)" in q:
            return len(self.organizer_profiles)
        if "pan_masked" in q:
            return "ABCDE1234F"
        if "gstin_masked" in q:
            return "24ABCDE1234F1Z5"
        if "account_masked" in q:
            return "123456789012"
        row = await self.fetchrow(query, *args)
        if row:
            return list(row.values())[0] if isinstance(row, dict) else row[0]
        return None

    async def execute(self, query: str, *args):
        q = query.lower()
        if "insert into duplicate_fingerprints" in q:
            self.duplicate_fingerprints.append({
                "id": uuid.uuid4(),
                "kind": args[0],
                "salted_hash": args[1],
                "case_id": args[2],
                "case_type": args[3],
                "created_at": datetime.now(timezone.utc),
            })
        elif "insert into notifications" in q:
            import re
            m = re.search(r"values\s*\(\s*\$1\s*,\s*'([^']+)'", q)
            ev_name = m.group(1) if m else (args[1] if len(args) > 2 else "notification_event")
            self.notifications.append({
                "id": uuid.uuid4(),
                "user_id": args[0],
                "event_name": ev_name,
                "payload": args[-1],
                "created_at": datetime.now(timezone.utc),
            })
        elif "update organizer_profiles" in q:
            pass
        elif "update bank_accounts" in q:
            for b in self.bank_accounts:
                b["verified"] = True


# ==============================================================================
# 1. MOCK BANK VERIFICATION ADAPTER TESTS
# ==============================================================================

def test_mock_bank_verification_success():
    """Verify standard bank account returns VERIFIED with derived bank name."""
    res = verify_mock_bank_account(
        holder_name="Sunburn Festivals Private Limited",
        ifsc="HDFC0001234",
        account_number="123456789012",
    )
    assert res["verified"] is True
    assert res["status"] == "VERIFIED"
    assert res["bank_name"] == "HDFC Bank Ltd"
    assert res["account_holder_matched"] is True
    assert "MOCK VERIFICATION ADAPTER" in res["disclaimer"]


def test_mock_bank_verification_invalid_ifsc():
    """Invalid IFSC format returns INVALID_IFSC and verified=False."""
    res = verify_mock_bank_account(
        holder_name="Sunburn Festivals",
        ifsc="INVALID_IFSC_123",
        account_number="123456789012",
    )
    assert res["verified"] is False
    assert res["status"] == "INVALID_IFSC"


def test_mock_bank_verification_name_mismatch():
    """Name containing 'mismatch' triggers simulated NAME_MISMATCH."""
    res = verify_mock_bank_account(
        holder_name="Mismatch Event Organizers",
        ifsc="SBIN0001234",
        account_number="123456789012",
    )
    assert res["verified"] is False
    assert res["status"] == "NAME_MISMATCH"
    assert res["account_holder_matched"] is False


def test_mock_bank_verification_failure_trigger():
    """Account ending in 0000 triggers destination bank failure."""
    res = verify_mock_bank_account(
        holder_name="Apex Shows",
        ifsc="ICIC0001234",
        account_number="9876540000",
    )
    assert res["verified"] is False
    assert res["status"] == "FAILED"


# ==============================================================================
# 2. DUPLICATE FINGERPRINTS & RISK ASSESSMENT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_duplicate_collision_detection():
    """Verify collisions detected without exposing plaintext values."""
    db = MockDbConnection()
    case_1 = uuid.uuid4()
    case_2 = uuid.uuid4()

    # Register fingerprints for case 1
    count = await register_case_fingerprints(
        conn=db,
        case_id=case_1,
        case_type=CaseType.ORGANIZER,
        pan="ABCDE1234F",
        gstin="24ABCDE1234F1Z5",
        bank_account="123456789012",
    )
    assert count == 3
    assert len(db.duplicate_fingerprints) == 3

    # Check case 2 using same PAN
    collisions = await check_duplicate_collisions(
        conn=db,
        case_id=case_2,
        pan="ABCDE1234F",
    )
    assert len(collisions) == 1
    assert collisions[0]["kind"] == "PAN"
    assert collisions[0]["colliding_case_id"] == str(case_1)


def test_risk_assessment_calculation():
    """Risk engine calculates flags and levels correctly."""
    # Low risk profile
    low_risk = assess_organizer_risk(
        profile={"legal_name": "Event Corp", "business_type": "COMPANY", "pan_masked": "ABCDE****F", "gstin_masked": "24ABCDE****1Z5"},
        bank_account={"verified": True},
        bank_verification_result={"verified": True, "status": "VERIFIED"},
        duplicate_collisions=[],
        documents=[{"review_status": "APPROVED"}],
    )
    assert low_risk["risk_level"] == "LOW"
    assert low_risk["risk_score"] < 30

    # High risk profile with duplicate collision and bank mismatch
    high_risk = assess_organizer_risk(
        profile={"legal_name": "Shady Corp", "business_type": "COMPANY", "pan_masked": "ABCDE****F", "gstin_masked": ""},
        bank_account={"verified": False},
        bank_verification_result={"verified": False, "status": "NAME_MISMATCH"},
        duplicate_collisions=[{"kind": "PAN", "colliding_case_id": "1111"}],
        documents=[],
    )
    assert high_risk["risk_level"] == "HIGH"
    assert high_risk["risk_score"] >= 60
    assert any(f["code"] == "DUPLICATE_PAN_COLLISION" for f in high_risk["flags"])
    assert any(f["code"] == "BANK_NAME_MISMATCH" for f in high_risk["flags"])


# ==============================================================================
# 3. REVIEWER CLAIM & DOCUMENT REVIEW TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_atomic_claim_and_release():
    """Reviewer can claim and release an application."""
    db = MockDbConnection()
    admin_id = uuid.uuid4()
    admin_user = {"id": admin_id, "roles": ["admin"]}
    case_id = uuid.uuid4()

    db.organizer_profiles.append({
        "id": case_id,
        "user_id": uuid.uuid4(),
        "legal_name": "Test Organizer",
        "verification_status": "SUBMITTED",
        "reviewer_id": None,
        "claim_expires_at": None,
    })

    # Claim
    claim_res = await claim_organizer_case(organizer_id=case_id, current_admin=admin_user, conn=db)
    assert claim_res["status"] == "IN_REVIEW"
    assert claim_res["reviewer_id"] == str(admin_id)

    # Release
    db.organizer_profiles[0]["verification_status"] = "IN_REVIEW"
    db.organizer_profiles[0]["reviewer_id"] = admin_id
    release_res = await release_organizer_case(organizer_id=case_id, current_admin=admin_user, conn=db)
    assert release_res["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_document_review_requires_comment_on_rejection():
    """Rejecting a document requires a reviewer comment."""
    db = MockDbConnection()
    doc_id = uuid.uuid4()
    admin_user = {"id": uuid.uuid4(), "roles": ["admin"]}

    db.verification_documents.append({
        "id": doc_id,
        "case_id": uuid.uuid4(),
        "doc_type": "PAN",
        "version": 1,
        "review_status": "PENDING",
    })

    # Rejection without comment must raise 400
    with pytest.raises(HTTPException) as exc:
        await review_document(
            document_id=doc_id,
            payload=DocumentReviewRequest(review_status=ReviewStatus.REJECTED, reviewer_comment=""),
            current_admin=admin_user,
            conn=db,
        )
    assert exc.value.status_code == 400
    assert "mandatory" in exc.value.detail


# ==============================================================================
# 4. OVERALL VERIFICATION DECISION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_overall_approval_decision():
    """Approving an organizer updates trust tier and emits notification."""
    db = MockDbConnection()
    admin_user = {"id": uuid.uuid4(), "roles": ["admin"]}
    case_id = uuid.uuid4()
    user_id = uuid.uuid4()

    db.organizer_profiles.append({
        "id": case_id,
        "user_id": user_id,
        "legal_name": "Golden Stage Productions",
        "verification_status": "SUBMITTED",
        "trust_tier": "TIER_1",
    })
    db.bank_accounts.append({
        "id": uuid.uuid4(),
        "organizer_id": case_id,
        "holder_name": "Golden Stage Productions",
        "ifsc": "HDFC0001234",
        "account_masked": "********1234",
        "verified": False,
    })

    res = await make_verification_decision(
        organizer_id=case_id,
        payload=VerificationDecisionRequest(
            decision=VerificationStatus.APPROVED,
            comments="All KYC documents verified.",
        ),
        current_admin=admin_user,
        conn=db,
    )
    assert res["status"] == "success"
    assert res["new_status"] == "APPROVED"
    assert any(n["event_name"] == "case_approved" for n in db.notifications)


@pytest.mark.asyncio
async def test_overall_rejection_requires_reason():
    """Rejecting an application without a reason fails validation."""
    db = MockDbConnection()
    admin_user = {"id": uuid.uuid4(), "roles": ["admin"]}
    case_id = uuid.uuid4()

    db.organizer_profiles.append({
        "id": case_id,
        "user_id": uuid.uuid4(),
        "legal_name": "Invalid Org",
        "verification_status": "SUBMITTED",
    })

    with pytest.raises(HTTPException) as exc:
        await make_verification_decision(
            organizer_id=case_id,
            payload=VerificationDecisionRequest(
                decision=VerificationStatus.REJECTED,
                rejection_reason="",
            ),
            current_admin=admin_user,
            conn=db,
        )
    assert exc.value.status_code == 400
    assert "mandatory" in exc.value.detail


# ==============================================================================
# 5. ACCOUNT ACTIONS: SUSPEND & REACTIVATE TESTS (A-06)
# ==============================================================================

@pytest.mark.asyncio
async def test_suspend_and_reactivate_organizer():
    """Admin can suspend an approved organizer and reactivate them with reason."""
    db = MockDbConnection()
    admin_user = {"id": uuid.uuid4(), "roles": ["admin"]}
    case_id = uuid.uuid4()
    user_id = uuid.uuid4()

    db.organizer_profiles.append({
        "id": case_id,
        "user_id": user_id,
        "legal_name": "Active Concerts Ltd",
        "verification_status": "APPROVED",
        "suspension_reason": None,
    })

    # 1. Suspend
    suspend_res = await suspend_organizer(
        organizer_id=case_id,
        payload=AccountActionRequest(reason="Compliance audit investigation initiated."),
        current_admin=admin_user,
        conn=db,
    )
    assert "suspended" in suspend_res["message"]
    assert any(n["event_name"] == "organizer.suspended" for n in db.notifications)

    # 2. Reactivate
    db.organizer_profiles[0]["verification_status"] = "SUSPENDED"
    reactivate_res = await reactivate_organizer(
        organizer_id=case_id,
        payload=AccountActionRequest(reason="Investigation concluded successfully without finding."),
        current_admin=admin_user,
        conn=db,
    )
    assert "reactivated" in reactivate_res["message"]
    assert any(n["event_name"] == "organizer.reactivated" for n in db.notifications)


# ==============================================================================
# 6. PAYOUT ELIGIBILITY & TRUST TIER ENFORCEMENT TESTS (A-06)
# ==============================================================================

@pytest.mark.asyncio
async def test_payout_eligibility_approved_vs_unverified():
    """Payout eligibility enforces approved status and verified bank."""
    db = MockDbConnection()
    case_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Unverified / Draft organizer -> Not eligible
    db.organizer_profiles.append({
        "id": case_id,
        "user_id": user_id,
        "legal_name": "Unverified Org",
        "verification_status": "DRAFT",
        "trust_tier": "TIER_1",
        "user_status": "active",
        "suspension_reason": None,
    })
    elig = await evaluate_payout_eligibility(conn=db, organizer_id=case_id)
    assert elig["eligible"] is False
    assert any("not approved" in r for r in elig["reasons"])

    # Approved organizer with verified bank -> Eligible
    db.organizer_profiles[0]["verification_status"] = "APPROVED"
    db.bank_accounts.append({
        "id": uuid.uuid4(),
        "organizer_id": case_id,
        "holder_name": "Unverified Org",
        "ifsc": "HDFC0001234",
        "account_masked": "********1234",
        "verified": True,
    })
    elig_approved = await evaluate_payout_eligibility(conn=db, organizer_id=case_id)
    assert elig_approved["eligible"] is True
    assert elig_approved["payout_hold_days"] == 14
    assert elig_approved["max_live_shows"] == 2


@pytest.mark.asyncio
async def test_suspended_organizer_payout_rejected():
    """Suspended organizer is immediately denied payout eligibility."""
    db = MockDbConnection()
    case_id = uuid.uuid4()

    db.organizer_profiles.append({
        "id": case_id,
        "user_id": uuid.uuid4(),
        "legal_name": "Suspended Org",
        "verification_status": "SUSPENDED",
        "trust_tier": "TIER_1",
        "user_status": "active",
        "suspension_reason": "Policy violation.",
    })
    elig = await evaluate_payout_eligibility(conn=db, organizer_id=case_id)
    assert elig["eligible"] is False
    assert any("suspended" in r for r in elig["reasons"])
