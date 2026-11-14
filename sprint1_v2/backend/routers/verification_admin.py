from __future__ import annotations

from typing import Optional, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user, require_role
from services.verification import claim_case, log_action, transition_case


router = APIRouter(prefix="/api/admin/verification", tags=["admin-verification"])

Reviewer = Depends(require_role("verification_reviewer", "platform_admin"))
PlatformAdmin = Depends(require_role("platform_admin"))


class DecisionBody(BaseModel):
    action: Literal["request_changes", "approve", "reject"]
    reason: str = Field(default="", max_length=2000)
    expected_version: Optional[int] = Field(default=None, ge=1)


@router.get("/queue")
async def list_queue(
    status: Optional[Literal["SUBMITTED", "IN_REVIEW", "CHANGES_REQUESTED"]] = None,
    case_type: Optional[Literal["ORGANIZER", "VENUE", "LISTING"]] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: dict = Reviewer,
    conn: asyncpg.Connection = Depends(get_conn),
):
    offset = (page - 1) * page_size

    rows = await conn.fetch(
        """
        SELECT c.id, c.case_type, c.subject_id, c.applicant_user_id,
               c.status, c.submitted_at, c.claimed_by, c.claim_expires_at,
               c.row_version, u.name AS applicant_name,
               CASE
                 WHEN c.claim_expires_at IS NULL THEN false
                 WHEN c.claim_expires_at <= now() THEN false
                 ELSE true
               END AS is_claimed
        FROM public.verification_cases c
        JOIN public.users u ON u.id = c.applicant_user_id
        WHERE ($1::varchar IS NULL OR c.status = $1)
          AND ($2::varchar IS NULL OR c.case_type = $2)
          AND c.status IN ('SUBMITTED', 'IN_REVIEW', 'CHANGES_REQUESTED')
        ORDER BY c.submitted_at ASC NULLS LAST, c.created_at ASC
        LIMIT $3 OFFSET $4
        """,
        status,
        case_type,
        page_size,
        offset,
    )

    total = await conn.fetchval(
        """
        SELECT count(*)
        FROM public.verification_cases c
        WHERE ($1::varchar IS NULL OR c.status = $1)
          AND ($2::varchar IS NULL OR c.case_type = $2)
          AND c.status IN ('SUBMITTED', 'IN_REVIEW', 'CHANGES_REQUESTED')
        """,
        status,
        case_type,
    )

    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/cases/{case_id}/claim")
async def claim(
    case_id: UUID,
    current_user: dict = Reviewer,
    conn: asyncpg.Connection = Depends(get_conn),
):
    roles = current_user.get("roles", [])
    actor_role = "platform_admin" if "platform_admin" in roles else "verification_reviewer"

    return await claim_case(
        conn,
        case_id=case_id,
        actor_id=UUID(str(current_user["id"])),
        actor_role=actor_role,
    )


@router.post("/cases/{case_id}/release")
async def release(
    case_id: UUID,
    current_user: dict = Reviewer,
    conn: asyncpg.Connection = Depends(get_conn),
):
    actor_id = UUID(str(current_user["id"]))
    roles = current_user.get("roles", [])
    actor_role = "platform_admin" if "platform_admin" in roles else "verification_reviewer"

    async with conn.transaction():
        row = await conn.fetchrow(
            """
            SELECT id, status, claimed_by, row_version
            FROM public.verification_cases
            WHERE id = $1
            FOR UPDATE
            """,
            case_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Verification case not found")
        if row["status"] != "IN_REVIEW" or row["claimed_by"] != actor_id:
            raise HTTPException(status_code=409, detail="You do not hold this case claim")

        await conn.execute(
            """
            UPDATE public.verification_cases
            SET claimed_by = NULL,
                claim_expires_at = NULL,
                row_version = row_version + 1,
                updated_at = now()
            WHERE id = $1
            """,
            case_id,
        )

        await log_action(
            conn,
            actor_id=actor_id,
            actor_role=actor_role,
            action="release",
            entity_type="verification_case",
            entity_id=case_id,
            before={"claimed_by": str(actor_id)},
            after={"claimed_by": None},
        )

    return {"id": str(case_id), "released": True}


@router.post("/cases/{case_id}/decision")
async def decide(
    case_id: UUID,
    body: DecisionBody,
    current_user: dict = Reviewer,
    conn: asyncpg.Connection = Depends(get_conn),
):
    roles = current_user.get("roles", [])
    actor_role = "platform_admin" if "platform_admin" in roles else "verification_reviewer"

    return await transition_case(
        conn,
        case_id=case_id,
        action=body.action,
        actor_id=UUID(str(current_user["id"])),
        actor_role=actor_role,
        reason=body.reason,
        expected_version=body.expected_version,
    )


@router.get("/audit-log")
async def list_audit_log(
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: dict = PlatformAdmin,
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        SELECT id, actor_id, actor_role, action, entity_type, entity_id,
               before, after, reason, at
        FROM public.audit_log
        WHERE ($1::varchar IS NULL OR entity_type = $1)
          AND ($2::uuid IS NULL OR entity_id = $2)
        ORDER BY at DESC
        LIMIT $3 OFFSET $4
        """,
        entity_type,
        entity_id,
        page_size,
        (page - 1) * page_size,
    )
    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
    }