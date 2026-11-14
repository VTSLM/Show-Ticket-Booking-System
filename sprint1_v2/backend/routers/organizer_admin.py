"""
Admin Organizer Verification & Management Router — Sprint 2.
Person A: Deliverables A-05 (Admin Review Workspace) & A-06 (Organizer Directory & Management).

Exposes:
- Reviewer queue, atomic claim, and release.
- Application details inspection with private document viewer URLs.
- Risk assessment and duplicate collision evaluation.
- Individual document decisions and comments.
- Overall verification decisions (APPROVED, REJECTED, CHANGES_REQUESTED).
- Organizer directory with search, filtering, and trust tiers.
- Authorized account actions (suspend, reactivate).
- Payout eligibility determination.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import require_role
from models.verification import ReviewStatus, VerificationStatus
from services.bank_verification import verify_mock_bank_account
from services.document_vault import get_view_url
from services.duplicate_detection import check_duplicate_collisions, register_case_fingerprints
from services.risk_assessment import assess_organizer_risk
from services.trust_tier_service import evaluate_payout_eligibility, get_trust_tier_rules

router = APIRouter(prefix="/api/admin/organizers", tags=["Admin Organizer Management"])


class DocumentReviewRequest(BaseModel):
    review_status: ReviewStatus
    reviewer_comment: Optional[str] = None


class VerificationDecisionRequest(BaseModel):
    decision: VerificationStatus
    comments: Optional[str] = None
    rejection_reason: Optional[str] = None


class AccountActionRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


# ==============================================================================
# A-05: REVIEW WORKSPACE & QUEUE
# ==============================================================================

@router.get("/reviews", summary="Get organizer verification review queue")
async def get_review_queue(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    List organizer applications pending review or currently in review.
    Enforces role checking: admin only.
    """
    where_clauses = ["o.verification_status IN ('SUBMITTED', 'IN_REVIEW', 'CHANGES_REQUESTED')"]
    params = []

    if status_filter:
        params.append(status_filter.upper())
        where_clauses = ["o.verification_status = $1"]

    where_sql = " AND ".join(where_clauses)
    query = f"""
        SELECT o.id, o.user_id, o.legal_name, o.business_type, o.state, o.pan_masked,
               o.gstin_masked, o.verification_status, o.trust_tier, o.reviewer_id,
               o.claimed_at, o.claim_expires_at, o.reviewer_comments, o.rejection_reason,
               o.created_at, o.updated_at,
               u.name as applicant_name, u.email as applicant_email,
               r.name as reviewer_name
        FROM organizer_profiles o
        JOIN users u ON u.id = o.user_id
        LEFT JOIN users r ON r.id = o.reviewer_id
        WHERE {where_sql}
        ORDER BY o.updated_at DESC
    """
    rows = await conn.fetch(query, *params)

    items = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["user_id"] = str(d["user_id"])
        if d.get("reviewer_id"):
            d["reviewer_id"] = str(d["reviewer_id"])
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        if d.get("claimed_at"):
            d["claimed_at"] = d["claimed_at"].isoformat()
        if d.get("claim_expires_at"):
            d["claim_expires_at"] = d["claim_expires_at"].isoformat()
        items.append(d)

    return {
        "count": len(items),
        "cases": items,
    }


@router.get("/{organizer_id}", summary="Get full organizer verification review workspace")
async def get_organizer_review_workspace(
    organizer_id: uuid.UUID,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Retrieve all details for reviewing an organizer application:
    - Profile & business details
    - Masked bank details & mock verification status
    - Documents with review statuses & temporary signed URLs
    - Duplicate fingerprint collisions
    - Advisory risk assessment report
    """
    profile_row = await conn.fetchrow(
        """
        SELECT o.*, u.name as applicant_name, u.email as applicant_email, u.phone as applicant_phone,
               u.status as user_status, r.name as reviewer_name
        FROM organizer_profiles o
        JOIN users u ON u.id = o.user_id
        LEFT JOIN users r ON r.id = o.reviewer_id
        WHERE o.id = $1
        """,
        organizer_id,
    )
    if not profile_row:
        raise HTTPException(status_code=404, detail="Organizer application not found")

    prof = dict(profile_row)

    # 1. Bank account
    bank_row = await conn.fetchrow(
        """
        SELECT id, holder_name, ifsc, account_masked, account_hash, verified, created_at, updated_at
        FROM bank_accounts
        WHERE organizer_id = $1
        ORDER BY created_at DESC LIMIT 1
        """,
        organizer_id,
    )
    bank_dict = dict(bank_row) if bank_row else None
    bank_verification = None
    if bank_dict:
        bank_dict["id"] = str(bank_dict["id"])
        if bank_dict.get("created_at"):
            bank_dict["created_at"] = bank_dict["created_at"].isoformat()
        if bank_dict.get("updated_at"):
            bank_dict["updated_at"] = bank_dict["updated_at"].isoformat()

        # Execute mock bank verification check
        bank_verification = verify_mock_bank_account(
            holder_name=bank_dict["holder_name"],
            ifsc=bank_dict["ifsc"],
            account_hash=bank_dict["account_hash"],
        )

    # 2. Documents
    doc_rows = await conn.fetch(
        """
        SELECT d.*, u.name as reviewer_name
        FROM verification_documents d
        LEFT JOIN users u ON u.id = d.reviewed_by
        WHERE d.case_id = $1
        ORDER BY d.doc_type, d.version DESC
        """,
        organizer_id,
    )
    docs = []
    for d in doc_rows:
        dd = dict(d)
        dd["id"] = str(dd["id"])
        dd["case_id"] = str(dd["case_id"])
        if dd.get("uploaded_by"):
            dd["uploaded_by"] = str(dd["uploaded_by"])
        if dd.get("reviewed_by"):
            dd["reviewed_by"] = str(dd["reviewed_by"])
        if dd.get("valid_to"):
            dd["valid_to"] = dd["valid_to"].isoformat()
        if dd.get("uploaded_at"):
            dd["uploaded_at"] = dd["uploaded_at"].isoformat()
        if dd.get("reviewed_at"):
            dd["reviewed_at"] = dd["reviewed_at"].isoformat()

        # Generate safe temporary signed view URL for reviewer
        try:
            url_res = await get_view_url(conn=conn, document_id=uuid.UUID(dd["id"]), user=current_admin)
            dd["view_url"] = url_res.get("signed_url")
            dd["url_expires_at"] = url_res.get("expires_at")
        except Exception:
            dd["view_url"] = None

        docs.append(dd)

    # 3. Duplicate Collisions Check (Anti-fraud)
    pan = prof.get("pan_masked")
    gstin = prof.get("gstin_masked")
    bank_acc = bank_dict.get("account_masked") if bank_dict else None
    collisions = await check_duplicate_collisions(
        conn=conn,
        case_id=organizer_id,
        pan=pan,
        gstin=gstin,
        bank_account=bank_acc,
    )

    # 4. Risk Assessment
    risk_assessment = assess_organizer_risk(
        profile=prof,
        bank_account=bank_dict,
        bank_verification_result=bank_verification,
        duplicate_collisions=collisions,
        documents=docs,
    )

    # Format profile response
    prof["id"] = str(prof["id"])
    prof["user_id"] = str(prof["user_id"])
    if prof.get("reviewer_id"):
        prof["reviewer_id"] = str(prof["reviewer_id"])
    if prof.get("created_at"):
        prof["created_at"] = prof["created_at"].isoformat()
    if prof.get("updated_at"):
        prof["updated_at"] = prof["updated_at"].isoformat()
    if prof.get("claimed_at"):
        prof["claimed_at"] = prof["claimed_at"].isoformat()
    if prof.get("claim_expires_at"):
        prof["claim_expires_at"] = prof["claim_expires_at"].isoformat()

    return {
        "organizer": prof,
        "bank_account": bank_dict,
        "bank_verification": bank_verification,
        "documents": docs,
        "duplicate_collisions": collisions,
        "risk_assessment": risk_assessment,
    }


@router.post("/{organizer_id}/claim", summary="Atomically claim an organizer application for review")
async def claim_organizer_case(
    organizer_id: uuid.UUID,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Atomically claims an application for 30 minutes.
    Prevents race conditions between simultaneous reviewers.
    """
    admin_id = current_admin["id"]

    async with conn.transaction():
        # Check current status & claim
        prof = await conn.fetchrow(
            """
            SELECT id, verification_status, reviewer_id, claim_expires_at
            FROM organizer_profiles
            WHERE id = $1 FOR UPDATE
            """,
            organizer_id,
        )
        if not prof:
            raise HTTPException(status_code=404, detail="Organizer application not found")

        curr_status = prof["verification_status"]
        if curr_status not in ("SUBMITTED", "IN_REVIEW", "CHANGES_REQUESTED"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot claim application in '{curr_status}' state.",
            )

        # Check if claimed by someone else and not expired
        now = datetime.now(timezone.utc)
        if (
            prof["reviewer_id"]
            and str(prof["reviewer_id"]) != str(admin_id)
            and prof["claim_expires_at"]
            and prof["claim_expires_at"] > now
        ):
            raise HTTPException(
                status_code=409,
                detail="Case is already claimed by another reviewer. Please choose another case.",
            )

        # Update claim atomically
        updated = await conn.fetchrow(
            """
            UPDATE organizer_profiles
            SET reviewer_id = $1,
                claimed_at = now(),
                claim_expires_at = now() + interval '30 minutes',
                verification_status = 'IN_REVIEW',
                updated_at = now()
            WHERE id = $2
            RETURNING id, reviewer_id, claimed_at, claim_expires_at, verification_status
            """,
            admin_id,
            organizer_id,
        )

    return {
        "message": "Case claimed successfully",
        "case_id": str(updated["id"]),
        "reviewer_id": str(updated["reviewer_id"]),
        "status": updated["verification_status"],
        "claimed_at": updated["claimed_at"].isoformat(),
        "claim_expires_at": updated["claim_expires_at"].isoformat(),
    }


@router.post("/{organizer_id}/release", summary="Release a claimed application back to review queue")
async def release_organizer_case(
    organizer_id: uuid.UUID,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """Release claim on an application, returning it to SUBMITTED state."""
    admin_id = current_admin["id"]

    prof = await conn.fetchrow(
        "SELECT id, verification_status, reviewer_id FROM organizer_profiles WHERE id = $1",
        organizer_id,
    )
    if not prof:
        raise HTTPException(status_code=404, detail="Organizer application not found")

    if prof["reviewer_id"] and str(prof["reviewer_id"]) != str(admin_id) and "admin" not in current_admin.get("roles", []):
        raise HTTPException(status_code=403, detail="You can only release cases claimed by yourself")

    updated = await conn.fetchrow(
        """
        UPDATE organizer_profiles
        SET reviewer_id = NULL,
            claimed_at = NULL,
            claim_expires_at = NULL,
            verification_status = 'SUBMITTED',
            updated_at = now()
        WHERE id = $1
        RETURNING id, verification_status
        """,
        organizer_id,
    )

    return {
        "message": "Case released back to review queue",
        "case_id": str(updated["id"]),
        "status": updated["verification_status"],
    }


@router.post("/documents/{document_id}/review", summary="Review an individual verification document")
async def review_document(
    document_id: uuid.UUID,
    payload: DocumentReviewRequest,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Approve, reject, or request changes on a specific document.
    Requires comment if rejected or changes requested.
    """
    if payload.review_status in (ReviewStatus.REJECTED, ReviewStatus.CHANGES_REQUESTED):
        if not payload.reviewer_comment or not payload.reviewer_comment.strip():
            raise HTTPException(
                status_code=400,
                detail="A reviewer comment is mandatory when rejecting or requesting changes on a document.",
            )

    doc = await conn.fetchrow(
        "SELECT id, case_id, doc_type, version, review_status FROM verification_documents WHERE id = $1",
        document_id,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Verification document not found")

    updated = await conn.fetchrow(
        """
        UPDATE verification_documents
        SET review_status = $1,
            reviewer_comment = $2,
            reviewed_by = $3,
            reviewed_at = now()
        WHERE id = $4
        RETURNING id, case_id, doc_type, version, review_status, reviewer_comment, reviewed_at
        """,
        payload.review_status.value,
        payload.reviewer_comment.strip() if payload.reviewer_comment else None,
        current_admin["id"],
        document_id,
    )

    return {
        "message": f"Document {updated['doc_type']} status updated to {updated['review_status']}",
        "document": {
            "id": str(updated["id"]),
            "case_id": str(updated["case_id"]),
            "doc_type": updated["doc_type"],
            "version": updated["version"],
            "review_status": updated["review_status"],
            "reviewer_comment": updated["reviewer_comment"],
            "reviewed_at": updated["reviewed_at"].isoformat() if updated["reviewed_at"] else None,
        },
    }


@router.post("/{organizer_id}/decision", summary="Make overall verification decision on an application")
async def make_verification_decision(
    organizer_id: uuid.UUID,
    payload: VerificationDecisionRequest,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Make final verification decision:
    - APPROVED: Transitions to APPROVED, assigns trust tier TIER_1, registers duplicate fingerprints, logs notification.
    - REJECTED: Requires rejection_reason. Transitions to REJECTED, logs notification.
    - CHANGES_REQUESTED: Requires comments. Transitions to CHANGES_REQUESTED, logs notification.
    """
    decision = payload.decision
    if decision not in (VerificationStatus.APPROVED, VerificationStatus.REJECTED, VerificationStatus.CHANGES_REQUESTED):
        raise HTTPException(
            status_code=400,
            detail="Decision must be APPROVED, REJECTED, or CHANGES_REQUESTED",
        )

    if decision == VerificationStatus.REJECTED and not (payload.rejection_reason or "").strip():
        raise HTTPException(status_code=400, detail="Rejection reason is mandatory when rejecting an application")

    if decision == VerificationStatus.CHANGES_REQUESTED and not (payload.comments or "").strip():
        raise HTTPException(status_code=400, detail="Instructions/comments are mandatory when requesting changes")

    prof = await conn.fetchrow(
        "SELECT id, user_id, legal_name, verification_status, trust_tier FROM organizer_profiles WHERE id = $1",
        organizer_id,
    )
    if not prof:
        raise HTTPException(status_code=404, detail="Organizer application not found")

    curr_status = prof["verification_status"]
    if curr_status not in ("SUBMITTED", "IN_REVIEW"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot make decision on application currently in '{curr_status}' state.",
        )

    user_id = prof["user_id"]
    assigned_tier = prof["trust_tier"] or "TIER_1"

    async with conn.transaction():
        if decision == VerificationStatus.APPROVED:
            # 1. Update profile
            await conn.execute(
                """
                UPDATE organizer_profiles
                SET verification_status = 'APPROVED',
                    trust_tier = $1,
                    reviewer_comments = $2,
                    rejection_reason = NULL,
                    updated_at = now()
                WHERE id = $3
                """,
                assigned_tier,
                payload.comments.strip() if payload.comments else "Application approved",
                organizer_id,
            )

            # 2. Mark bank account verified
            await conn.execute(
                "UPDATE bank_accounts SET verified = true, updated_at = now() WHERE organizer_id = $1",
                organizer_id,
            )

            # 3. Register duplicate collision fingerprints
            pan_val = await conn.fetchval("SELECT pan_masked FROM organizer_profiles WHERE id = $1", organizer_id)
            gstin_val = await conn.fetchval("SELECT gstin_masked FROM organizer_profiles WHERE id = $1", organizer_id)
            bank_val = await conn.fetchval("SELECT account_masked FROM bank_accounts WHERE organizer_id = $1", organizer_id)
            await register_case_fingerprints(
                conn=conn,
                case_id=organizer_id,
                pan=pan_val,
                gstin=gstin_val,
                bank_account=bank_val,
            )

            # 4. Emit notification: case_approved
            notif_payload = json.dumps({
                "case_id": str(organizer_id),
                "legal_name": prof["legal_name"],
                "status": "APPROVED",
                "trust_tier": assigned_tier,
                "comments": payload.comments or "Your organizer verification has been approved.",
            })
            await conn.execute(
                "INSERT INTO notifications (user_id, event_name, payload) VALUES ($1, 'case_approved', $2::jsonb)",
                user_id,
                notif_payload,
            )

        elif decision == VerificationStatus.REJECTED:
            # Update profile
            await conn.execute(
                """
                UPDATE organizer_profiles
                SET verification_status = 'REJECTED',
                    rejection_reason = $1,
                    reviewer_comments = $2,
                    updated_at = now()
                WHERE id = $3
                """,
                payload.rejection_reason.strip(),
                payload.comments.strip() if payload.comments else None,
                organizer_id,
            )

            # Emit notification: case_rejected
            notif_payload = json.dumps({
                "case_id": str(organizer_id),
                "legal_name": prof["legal_name"],
                "status": "REJECTED",
                "rejection_reason": payload.rejection_reason.strip(),
            })
            await conn.execute(
                "INSERT INTO notifications (user_id, event_name, payload) VALUES ($1, 'case_rejected', $2::jsonb)",
                user_id,
                notif_payload,
            )

        elif decision == VerificationStatus.CHANGES_REQUESTED:
            # Update profile
            await conn.execute(
                """
                UPDATE organizer_profiles
                SET verification_status = 'CHANGES_REQUESTED',
                    reviewer_comments = $1,
                    updated_at = now()
                WHERE id = $2
                """,
                payload.comments.strip(),
                organizer_id,
            )

            # Emit notification: changes_requested
            notif_payload = json.dumps({
                "case_id": str(organizer_id),
                "legal_name": prof["legal_name"],
                "status": "CHANGES_REQUESTED",
                "instructions": payload.comments.strip(),
            })
            await conn.execute(
                "INSERT INTO notifications (user_id, event_name, payload) VALUES ($1, 'changes_requested', $2::jsonb)",
                user_id,
                notif_payload,
            )

    return {
        "status": "success",
        "message": f"Verification decision '{decision.value}' recorded successfully.",
        "case_id": str(organizer_id),
        "new_status": decision.value,
    }


# ==============================================================================
# A-06: ORGANIZER DIRECTORY & ACCOUNT MANAGEMENT
# ==============================================================================

@router.get("", summary="Admin Organizer Directory with search and filtering")
async def list_organizers(
    q: Optional[str] = Query(None, description="Search query by name, state, or email"),
    status: Optional[str] = Query(None, description="Filter by verification status"),
    tier: Optional[str] = Query(None, description="Filter by trust tier"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Search and filter registered organizers across all verification and account states.
    Authorized for administrators.
    """
    conditions = ["1=1"]
    args = []

    if q and q.strip():
        args.append(f"%{q.strip()}%")
        idx = len(args)
        conditions.append(f"(o.legal_name ILIKE ${idx} OR o.state ILIKE ${idx} OR u.email ILIKE ${idx} OR u.name ILIKE ${idx})")

    if status and status.strip():
        args.append(status.strip().upper())
        idx = len(args)
        conditions.append(f"o.verification_status = ${idx}")

    if tier and tier.strip():
        args.append(tier.strip().upper())
        idx = len(args)
        conditions.append(f"o.trust_tier = ${idx}")

    where_sql = " AND ".join(conditions)

    # Count total
    total_count = await conn.fetchval(
        f"""
        SELECT count(*)
        FROM organizer_profiles o
        JOIN users u ON u.id = o.user_id
        WHERE {where_sql}
        """,
        *args,
    ) or 0

    # Fetch rows with pagination
    args.extend([limit, offset])
    query = f"""
        SELECT o.id, o.user_id, o.legal_name, o.business_type, o.state, o.pan_masked,
               o.gstin_masked, o.verification_status, o.trust_tier, o.suspension_reason,
               o.reviewer_comments, o.created_at, o.updated_at,
               u.name as contact_name, u.email as contact_email, u.phone as contact_phone,
               u.status as user_status,
               b.holder_name as bank_holder, b.account_masked, b.ifsc, b.verified as bank_verified
        FROM organizer_profiles o
        JOIN users u ON u.id = o.user_id
        LEFT JOIN LATERAL (
            SELECT holder_name, account_masked, ifsc, verified
            FROM bank_accounts
            WHERE organizer_id = o.id
            ORDER BY created_at DESC LIMIT 1
        ) b ON true
        WHERE {where_sql}
        ORDER BY o.created_at DESC
        LIMIT ${len(args) - 1} OFFSET ${len(args)}
    """
    rows = await conn.fetch(query, *args)

    results = []
    for r in rows:
        d = dict(r)
        d["id"] = str(d["id"])
        d["user_id"] = str(d["user_id"])
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        results.append(d)

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "organizers": results,
    }


@router.post("/{organizer_id}/suspend", summary="Suspend an organizer account with reason")
async def suspend_organizer(
    organizer_id: uuid.UUID,
    payload: AccountActionRequest,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Suspends an organizer's operational account.
    Restricted to platform administrators.
    Requires a detailed justification reason.
    """
    prof = await conn.fetchrow(
        "SELECT id, user_id, legal_name, verification_status FROM organizer_profiles WHERE id = $1",
        organizer_id,
    )
    if not prof:
        raise HTTPException(status_code=404, detail="Organizer not found")

    if prof["verification_status"] == VerificationStatus.SUSPENDED.value:
        raise HTTPException(status_code=400, detail="Organizer is already suspended")

    async with conn.transaction():
        updated = await conn.fetchrow(
            """
            UPDATE organizer_profiles
            SET verification_status = 'SUSPENDED',
                suspension_reason = $1,
                updated_at = now()
            WHERE id = $2
            RETURNING id, legal_name, verification_status, suspension_reason, updated_at
            """,
            payload.reason.strip(),
            organizer_id,
        )

        # Log notification
        notif_payload = json.dumps({
            "organizer_id": str(organizer_id),
            "legal_name": prof["legal_name"],
            "action": "SUSPENDED",
            "reason": payload.reason.strip(),
            "admin_id": str(current_admin["id"]),
        })
        await conn.execute(
            "INSERT INTO notifications (user_id, event_name, payload) VALUES ($1, 'organizer.suspended', $2::jsonb)",
            prof["user_id"],
            notif_payload,
        )

    return {
        "message": f"Organizer '{updated['legal_name']}' has been suspended.",
        "organizer_id": str(updated["id"]),
        "status": updated["verification_status"],
        "reason": updated["suspension_reason"],
        "updated_at": updated["updated_at"].isoformat(),
    }


@router.post("/{organizer_id}/reactivate", summary="Reactivate a suspended organizer account")
async def reactivate_organizer(
    organizer_id: uuid.UUID,
    payload: AccountActionRequest,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Reactivates a previously suspended organizer.
    Restricted to platform administrators.
    Restores status to APPROVED.
    """
    prof = await conn.fetchrow(
        "SELECT id, user_id, legal_name, verification_status FROM organizer_profiles WHERE id = $1",
        organizer_id,
    )
    if not prof:
        raise HTTPException(status_code=404, detail="Organizer not found")

    if prof["verification_status"] != VerificationStatus.SUSPENDED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reactivate organizer with current status '{prof['verification_status']}'. Only SUSPENDED accounts can be reactivated.",
        )

    async with conn.transaction():
        updated = await conn.fetchrow(
            """
            UPDATE organizer_profiles
            SET verification_status = 'APPROVED',
                suspension_reason = NULL,
                reviewer_comments = $1,
                updated_at = now()
            WHERE id = $2
            RETURNING id, legal_name, verification_status, updated_at
            """,
            f"Reactivated: {payload.reason.strip()}",
            organizer_id,
        )

        # Log notification
        notif_payload = json.dumps({
            "organizer_id": str(organizer_id),
            "legal_name": prof["legal_name"],
            "action": "REACTIVATED",
            "reason": payload.reason.strip(),
            "admin_id": str(current_admin["id"]),
        })
        await conn.execute(
            "INSERT INTO notifications (user_id, event_name, payload) VALUES ($1, 'organizer.reactivated', $2::jsonb)",
            prof["user_id"],
            notif_payload,
        )

    return {
        "message": f"Organizer '{updated['legal_name']}' has been reactivated.",
        "organizer_id": str(updated["id"]),
        "status": updated["verification_status"],
        "updated_at": updated["updated_at"].isoformat(),
    }


# ==============================================================================
# A-06: PAYOUT ELIGIBILITY ENDPOINT
# ==============================================================================

@router.get("/{organizer_id}/payout-eligibility", summary="Evaluate organizer payout settlement eligibility")
async def check_organizer_payout_eligibility(
    organizer_id: uuid.UUID,
    current_admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Evaluates payout settlement eligibility for an organizer based on verification status,
    trust tier rules, hold periods, and suspension state.
    """
    return await evaluate_payout_eligibility(conn=conn, organizer_id=organizer_id)

