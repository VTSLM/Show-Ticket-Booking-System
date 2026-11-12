from typing import Optional
from pathlib import Path
from uuid import UUID, uuid4
from datetime import date
import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from database import get_conn
from dependencies import get_current_user, require_role

router = APIRouter(
    prefix="/api/venue-verification",
    tags=["venue verification"],
)

DECISIONS = {"approved", "rejected", "changes_requested"}
PRIVATE_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "private_uploads"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

ALLOWED_UPLOAD_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


class VenueDraft(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    address: Optional[str] = None
    city: str = Field(min_length=2, max_length=100)
    state: Optional[str] = None
    pincode: Optional[str] = None
    licensed_capacity: Optional[int] = Field(default=None, gt=0)
    license_expiry: Optional[date] = None
    noc_expiry: Optional[date] = None


class DecisionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    decision: str
    reason: Optional[str] = None


def validate_decision(decision: str, reason: Optional[str]) -> None:
    if decision not in DECISIONS:
        raise HTTPException(status_code=422, detail="Invalid decision")

    if decision in {"rejected", "changes_requested"} and not (reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail="A reason is required for rejection or request changes",
        )


async def _check_case_access(conn: asyncpg.Connection, case_id: UUID, user: dict) -> None:
    case = await conn.fetchrow(
        """
        SELECT applicant_id
          FROM venue_verification_cases
         WHERE id = $1
        """,
        case_id,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Application not found")

    is_admin = "admin" in (user.get("roles") or [])
    is_applicant = str(case["applicant_id"]) == str(user["id"])

    if not (is_admin or is_applicant):
        raise HTTPException(status_code=404, detail="Application not found")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    body: VenueDraft,
    user: dict = Depends(require_role("manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    async with conn.transaction():
        venue = await conn.fetchrow(
            """
            INSERT INTO venues(
                name, address, city, state, pincode,
                verification_status, licensed_capacity, license_expiry, noc_expiry
            )
            VALUES ($1, $2, $3, $4, $5, 'unverified', $6, $7, $8)
            RETURNING id
            """,
            body.name.strip(),
            body.address.strip() if body.address else None,
            body.city.strip(),
            body.state.strip() if body.state else None,
            body.pincode.strip() if body.pincode else None,
            body.licensed_capacity,
            body.license_expiry,
            body.noc_expiry,
        )

        case = await conn.fetchrow(
            """
            INSERT INTO venue_verification_cases (venue_id, applicant_id)
            VALUES ($1, $2)
            RETURNING id, venue_id, status, version, created_at
            """,
            venue["id"],
            user["id"],
        )

    return dict(case)


@router.get("/mine")
async def my_applications(
    user: dict = Depends(require_role("manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        SELECT c.id, c.venue_id, c.status, c.version, c.reviewer_comments,
               c.created_at, c.updated_at,
               v.name, v.address, v.city, v.state, v.pincode,
               v.licensed_capacity, v.license_expiry, v.noc_expiry,
               v.verification_status
          FROM venue_verification_cases c
          JOIN venues v ON v.id = c.venue_id
         WHERE c.applicant_id = $1
         ORDER BY c.updated_at DESC
        """,
        user["id"],
    )
    return [dict(row) for row in rows]


@router.put("/{case_id}")
async def update_draft(
    case_id: UUID,
    body: VenueDraft,
    user: dict = Depends(require_role("manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    async with conn.transaction():
        case = await conn.fetchrow(
            """
            SELECT id, venue_id, status
              FROM venue_verification_cases
             WHERE id = $1 AND applicant_id = $2
             FOR UPDATE
            """,
            case_id,
            user["id"],
        )

        if case is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if case["status"] not in {"draft", "changes_requested"}:
            raise HTTPException(
                status_code=409,
                detail="Only drafts or applications needing changes can be edited",
            )

        await conn.execute(
            """
            UPDATE venues
               SET name = $2,
                   address = $3,
                   city = $4,
                   state = $5,
                   pincode = $6,
                   licensed_capacity = $7,
                   license_expiry = $8,
                   noc_expiry = $9
             WHERE id = $1
            """,
            case["venue_id"],
            body.name.strip(),
            body.address.strip() if body.address else None,
            body.city.strip(),
            body.state.strip() if body.state else None,
            body.pincode.strip() if body.pincode else None,
            body.licensed_capacity,
            body.license_expiry,
            body.noc_expiry,
        )

        updated = await conn.fetchrow(
            """
            UPDATE venue_verification_cases
               SET version = version + 1, updated_at = now()
             WHERE id = $1
             RETURNING id, venue_id, status, version, updated_at
            """,
            case_id,
        )

    return dict(updated)


@router.post("/{case_id}/submit")
async def submit_application(
    case_id: UUID,
    user: dict = Depends(require_role("manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    async with conn.transaction():
        case = await conn.fetchrow(
            """
            SELECT id, venue_id, status, version
              FROM venue_verification_cases
             WHERE id = $1 AND applicant_id = $2
             FOR UPDATE
            """,
            case_id,
            user["id"],
        )

        if case is None:
            raise HTTPException(status_code=404, detail="Application not found")
        if case["status"] not in {"draft", "changes_requested"}:
            raise HTTPException(status_code=409, detail="Application cannot be submitted")

        old_status = case["status"]
        new_version = case["version"] + 1

        await conn.execute(
            """
            UPDATE venue_verification_cases
               SET status = 'submitted',
                   reviewer_id = NULL,
                   claim_expires_at = NULL,
                   version = $2,
                   updated_at = now()
             WHERE id = $1
            """,
            case_id,
            new_version,
        )
        await conn.execute(
            "UPDATE venues SET verification_status = 'pending' WHERE id = $1",
            case["venue_id"],
        )
        await conn.execute(
            """
            INSERT INTO venue_verification_audit
                (case_id, case_version, actor_id, action, old_status, new_status)
            VALUES ($1, $2, $3, 'submitted', $4, 'submitted')
            """,
            case_id,
            new_version,
            user["id"],
            old_status,
        )

    return {"case_id": str(case_id), "status": "submitted", "version": new_version}


@router.post("/{case_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_case_document(
    case_id: UUID,
    kind: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(require_role("manager")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    if kind not in {"venue_photo", "seating_plan"}:
        raise HTTPException(
            status_code=422,
            detail="kind must be venue_photo or seating_plan",
        )

    case = await conn.fetchrow(
        """
        SELECT id, status
          FROM venue_verification_cases
         WHERE id = $1 AND applicant_id = $2
        """,
        case_id,
        user["id"],
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if case["status"] not in {"draft", "changes_requested"}:
        raise HTTPException(
            status_code=409,
            detail="Documents can only be uploaded to a draft or changes-requested case",
        )

    content_type = file.content_type or ""
    suffix = ALLOWED_UPLOAD_TYPES.get(content_type)
    if not suffix:
        raise HTTPException(
            status_code=415,
            detail="Upload a JPG, PNG, WEBP, or PDF file",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Maximum upload size is 8 MB")

    PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid4().hex}{suffix}"
    file_path = PRIVATE_UPLOAD_DIR / storage_key
    file_path.write_bytes(content)

    try:
        await conn.execute(
            """
            INSERT INTO venue_case_documents
                (case_id, uploaded_by, kind, original_filename,
                 content_type, size_bytes, storage_key)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (case_id, kind)
            DO UPDATE SET
                uploaded_by = EXCLUDED.uploaded_by,
                original_filename = EXCLUDED.original_filename,
                content_type = EXCLUDED.content_type,
                size_bytes = EXCLUDED.size_bytes,
                storage_key = EXCLUDED.storage_key,
                created_at = now()
            """,
            case_id,
            user["id"],
            kind,
            file.filename or "upload",
            content_type,
            len(content),
            storage_key,
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    return {
        "case_id": str(case_id),
        "kind": kind,
        "message": "File uploaded",
    }


@router.get("/{case_id}/documents")
async def list_case_documents(
    case_id: UUID,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _check_case_access(conn, case_id, user)

    rows = await conn.fetch(
        """
        SELECT id, kind, original_filename, content_type, size_bytes, created_at
          FROM venue_case_documents
         WHERE case_id = $1
         ORDER BY kind
        """,
        case_id,
    )
    return [dict(row) for row in rows]


@router.get("/{case_id}/documents/{document_id}/download")
async def download_case_document(
    case_id: UUID,
    document_id: UUID,
    user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    await _check_case_access(conn, case_id, user)

    row = await conn.fetchrow(
        """
        SELECT storage_key, original_filename, content_type
          FROM venue_case_documents
         WHERE id = $1 AND case_id = $2
        """,
        document_id,
        case_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    path = PRIVATE_UPLOAD_DIR / row["storage_key"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file was not found")

    return FileResponse(
        path,
        media_type=row["content_type"],
        filename=row["original_filename"],
        content_disposition_type="attachment",
    )


@router.get("/admin/queue")
async def review_queue(
    _: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        SELECT c.id, c.venue_id, c.applicant_id, c.status, c.version,
               c.reviewer_id, c.claim_expires_at, c.created_at, c.updated_at,
               v.name, v.city, v.verification_status
          FROM venue_verification_cases c
          JOIN venues v ON v.id = c.venue_id
         WHERE c.status IN ('submitted', 'in_review', 'changes_requested')
         ORDER BY c.created_at ASC
        """
    )
    return [dict(row) for row in rows]


@router.post("/admin/{case_id}/claim")
async def claim_case(
    case_id: UUID,
    admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    row = await conn.fetchrow(
        """
        UPDATE venue_verification_cases
           SET reviewer_id = $2,
               claim_expires_at = now() + interval '10 minutes',
               status = 'in_review',
               updated_at = now()
         WHERE id = $1
           AND status IN ('submitted', 'in_review')
           AND (
                reviewer_id IS NULL
                OR claim_expires_at <= now()
                OR reviewer_id = $2
           )
        RETURNING id, venue_id, status, reviewer_id, claim_expires_at, version
        """,
        case_id,
        admin["id"],
    )
    if row is not None:
        return dict(row)

    exists = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM venue_verification_cases WHERE id = $1)",
        case_id,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Review case not found")
    raise HTTPException(status_code=409, detail="Another reviewer has an active claim")


@router.get("/admin/{case_id}")
async def review_details(
    case_id: UUID,
    _: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    case = await conn.fetchrow(
        """
        SELECT c.id, c.venue_id, c.applicant_id, c.status, c.version,
               c.reviewer_id, c.claim_expires_at, c.reviewer_comments,
               v.name, v.address, v.city, v.state, v.pincode,
               v.licensed_capacity, v.license_expiry, v.noc_expiry,
               v.verification_status
          FROM venue_verification_cases c
          JOIN venues v ON v.id = c.venue_id
         WHERE c.id = $1
        """,
        case_id,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Review case not found")

    screens = await conn.fetch(
        """
        SELECT sc.id, sc.name, sc.capacity AS licensed_capacity,
               count(se.id)::int AS actual_seat_count
          FROM screens sc
          LEFT JOIN seats se ON se.screen_id = sc.id
         WHERE sc.venue_id = $1
         GROUP BY sc.id
         ORDER BY sc.name
        """,
        case["venue_id"],
    )

    return {
        "case": dict(case),
        "screens": [
            {
                **dict(screen),
                "capacity_mismatch": screen["licensed_capacity"] != screen["actual_seat_count"],
            }
            for screen in screens
        ],
    }


@router.post("/admin/{case_id}/decision")
async def decide_case(
    case_id: UUID,
    body: DecisionRequest,
    admin: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    validate_decision(body.decision, body.reason)

    async with conn.transaction():
        case = await conn.fetchrow(
            """
            SELECT id, venue_id, status, reviewer_id, claim_expires_at, version,
                   (claim_expires_at > now()) AS claim_active
              FROM venue_verification_cases
             WHERE id = $1
             FOR UPDATE
            """,
            case_id,
        )

        if case is None:
            raise HTTPException(status_code=404, detail="Review case not found")

        if case["version"] != body.expected_version:
            raise HTTPException(status_code=409, detail="Stale case version")

        if (
            case["status"] != "in_review"
            or case["reviewer_id"] != admin["id"]
            or not case["claim_active"]
        ):
            raise HTTPException(
                status_code=409,
                detail="You need an active claim to decide this case",
            )

        old_status = case["status"]
        new_version = case["version"] + 1

        venue_status = {
            "approved": "approved",
            "rejected": "rejected",
            "changes_requested": "changes_requested",
        }[body.decision]

        await conn.execute(
            """
            UPDATE venue_verification_cases
               SET status = $2,
                   reviewer_comments = $3,
                   reviewer_id = NULL,
                   claim_expires_at = NULL,
                   version = $4,
                   updated_at = now()
             WHERE id = $1
            """,
            case_id,
            body.decision,
            body.reason.strip() if body.reason else None,
            new_version,
        )

        await conn.execute(
            "UPDATE venues SET verification_status = $2 WHERE id = $1",
            case["venue_id"],
            venue_status,
        )

        await conn.execute(
            """
            INSERT INTO venue_verification_audit
                (case_id, case_version, actor_id, action, old_status, new_status, reason)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            case_id,
            new_version,
            admin["id"],
            body.decision,
            old_status,
            body.decision,
            body.reason.strip() if body.reason else None,
        )

    return {
        "case_id": str(case_id),
        "status": body.decision,
        "version": new_version,
    }


@router.get("/admin/{case_id}/audit")
async def audit_history(
    case_id: UUID,
    _: dict = Depends(require_role("admin")),
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await conn.fetch(
        """
        SELECT id, case_version, actor_id, action, old_status, new_status,
               reason, metadata, created_at
          FROM venue_verification_audit
         WHERE case_id = $1
         ORDER BY case_version
        """,
        case_id,
    )
    return [dict(row) for row in rows]
