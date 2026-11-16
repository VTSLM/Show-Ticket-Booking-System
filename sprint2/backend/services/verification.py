from __future__ import annotations

from typing import Optional, Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException


ALLOWED_TRANSITIONS = {
    ("DRAFT", "submit"): "SUBMITTED",
    ("SUBMITTED", "claim"): "IN_REVIEW",
    ("IN_REVIEW", "request_changes"): "CHANGES_REQUESTED",
    ("CHANGES_REQUESTED", "resubmit"): "SUBMITTED",
    ("IN_REVIEW", "approve"): "APPROVED",
    ("IN_REVIEW", "reject"): "REJECTED",
    ("APPROVED", "suspend"): "SUSPENDED",
    ("SUSPENDED", "resubmit"): "IN_REVIEW",
    ("APPROVED", "expire"): "EXPIRED",
}


async def log_action(
    conn: asyncpg.Connection,
    *,
    actor_id: Optional[UUID],
    actor_role: str,
    action: str,
    entity_type: str,
    entity_id: UUID,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
    reason: str = "",
) -> None:
    """Append one audit event. Never include document numbers or file contents."""
    await conn.execute(
        """
        INSERT INTO public.audit_log
            (actor_id, actor_role, action, entity_type, entity_id,
             before, after, reason, at)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, now())
        """,
        actor_id,
        actor_role,
        action,
        entity_type,
        entity_id,
        before,
        after,
        reason,
    )


async def transition_case(
    conn: asyncpg.Connection,
    *,
    case_id: UUID,
    action: str,
    actor_id: UUID,
    actor_role: str,
    reason: str = "",
    expected_version: Optional[int] = None,
) -> dict[str, Any]:
    """
    Run a state transition atomically.

    Decisions must come from the reviewer who currently holds the claim.
    Use a non-empty reason for reject, request_changes, and suspend.
    """
    if action not in {"request_changes", "approve", "reject", "suspend"}:
        raise HTTPException(status_code=400, detail="Unsupported case action")

    if action in {"request_changes", "reject", "suspend"} and not reason.strip():
        raise HTTPException(status_code=422, detail="A reason is required")

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT id, case_type, subject_id, applicant_user_id, status,
                   claimed_by, claim_expires_at, row_version
            FROM public.verification_cases
            WHERE id = $1
            FOR UPDATE
            """,
            case_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Verification case not found")

        before = dict(row)
        if expected_version is not None and row["row_version"] != expected_version:
            raise HTTPException(
                status_code=409,
                detail="Case changed since it was loaded; refresh and retry",
            )

        if row["status"] != "IN_REVIEW":
            raise HTTPException(status_code=409, detail="Case is not in review")

        if row["claimed_by"] != actor_id or row["claim_expires_at"] is None:
            raise HTTPException(status_code=409, detail="You do not hold this case claim")

        claim_is_active = await conn.fetchval(
            "SELECT $1::timestamptz > now()",
            row["claim_expires_at"],
        )
        if not claim_is_active:
            raise HTTPException(status_code=409, detail="Your case claim has expired")

        target_status = ALLOWED_TRANSITIONS.get((row["status"], action))
        if not target_status:
            raise HTTPException(status_code=409, detail="Transition is not allowed")

        updated = await conn.fetchrow(
            """
            UPDATE public.verification_cases
            SET status = $2,
                decided_by = $3,
                decided_at = now(),
                decision_reason = $4,
                claimed_by = NULL,
                claim_expires_at = NULL,
                row_version = row_version + 1,
                updated_at = now()
            WHERE id = $1
            RETURNING id, case_type, subject_id, applicant_user_id, status,
                      decided_by, decided_at, decision_reason, row_version
            """,
            case_id,
            target_status,
            actor_id,
            reason.strip(),
        )

        # Keep the venue's externally consumed status consistent.
        if row["case_type"] == "VENUE":
            await conn.execute(
                """
                UPDATE public.venues
                SET verification_status = $2, updated_at = now()
                WHERE id = $1
                """,
                row["subject_id"],
                target_status,
            )

        await log_action(
            conn,
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type="verification_case",
            entity_id=case_id,
            before={
                "status": row["status"],
                "row_version": row["row_version"],
            },
            after={
                "status": updated["status"],
                "row_version": updated["row_version"],
            },
            reason=reason.strip(),
        )

        return dict(updated)


async def claim_case(
    conn: asyncpg.Connection,
    *,
    case_id: UUID,
    actor_id: UUID,
    actor_role: str,
    claim_minutes: int = 15,
) -> dict[str, Any]:
    """Claim a submitted/unclaimed case, or reclaim an expired claim."""
    if not 1 <= claim_minutes <= 60:
        raise HTTPException(status_code=422, detail="Claim duration must be 1–60 minutes")

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT id, case_type, subject_id, status, claimed_by,
                   claim_expires_at, row_version
            FROM public.verification_cases
            WHERE id = $1
            FOR UPDATE
            """,
            case_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Verification case not found")

        if row["status"] not in {"SUBMITTED", "IN_REVIEW"}:
            raise HTTPException(status_code=409, detail="Case is not claimable")

        if row["claimed_by"] and row["claim_expires_at"]:
            if await conn.fetchval("SELECT $1::timestamptz > now()", row["claim_expires_at"]):
                raise HTTPException(status_code=409, detail="Case is already claimed")

        before = {
            "status": row["status"],
            "claimed_by": str(row["claimed_by"]) if row["claimed_by"] else None,
        }

        claimed = await conn.fetchrow(
            """
            UPDATE public.verification_cases
            SET status = 'IN_REVIEW',
                claimed_by = $2,
                claim_expires_at = now() + ($3 * interval '1 minute'),
                row_version = row_version + 1,
                updated_at = now()
            WHERE id = $1
            RETURNING id, case_type, subject_id, status, claimed_by,
                      claim_expires_at, row_version
            """,
            case_id,
            actor_id,
            claim_minutes,
        )

        if row["case_type"] == "VENUE":
            await conn.execute(
                "UPDATE public.venues SET verification_status = 'IN_REVIEW' WHERE id = $1",
                row["subject_id"],
            )

        await log_action(
            conn,
            actor_id=actor_id,
            actor_role=actor_role,
            action="claim",
            entity_type="verification_case",
            entity_id=case_id,
            before=before,
            after={
                "status": "IN_REVIEW",
                "claimed_by": str(actor_id),
                "row_version": claimed["row_version"],
            },
        )

        return dict(claimed)