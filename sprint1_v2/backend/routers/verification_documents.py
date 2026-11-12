"""
Verification Documents Router — Sprint 2.
Person A: A-03 Deliverable.

Exposes REST API endpoints for secure document upload and signed-URL viewing
under the agreed '/api/verification/...' applicant and shared namespace.
"""

from datetime import date
from typing import List, Optional
import uuid
import asyncpg
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from database import get_conn
from dependencies import get_current_user
from models.verification import CaseType, DocumentType
from services.document_vault import (
    upload_document,
    get_view_url,
    verify_case_access,
)

router = APIRouter(prefix="/api/verification", tags=["Verification Documents"])


@router.post(
    "/cases/{case_id}/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a verification document",
)
async def upload_case_document(
    case_id: uuid.UUID,
    file: UploadFile = File(...),
    doc_type: DocumentType = Form(...),
    case_type: CaseType = Form(CaseType.ORGANIZER),
    doc_number: Optional[str] = Form(None),
    issued_by: Optional[str] = Form(None),
    valid_to: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Upload a verification document to the private Supabase Storage vault.
    Allocates the next document version and records metadata.
    """
    file_bytes = await file.read()
    parsed_valid_to = None
    if valid_to:
        try:
            parsed_valid_to = date.fromisoformat(valid_to)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid valid_to date format. Expected YYYY-MM-DD",
            )

    doc_metadata = await upload_document(
        conn=conn,
        case_id=case_id,
        case_type=case_type,
        doc_type=doc_type,
        file_bytes=file_bytes,
        filename=file.filename or "document",
        user=current_user,
        content_type=file.content_type,
        doc_number=doc_number,
        issued_by=issued_by,
        valid_to=parsed_valid_to,
    )

    return doc_metadata


@router.get(
    "/documents/{document_id}/view",
    summary="Get temporary 5-minute signed URL for document viewing",
)
async def view_document_signed_url(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Generate a temporary signed URL for viewing a private document.
    Access is restricted to authorized applicants or reviewers.
    """
    return await get_view_url(
        conn=conn,
        document_id=document_id,
        user=current_user,
    )


@router.get(
    "/cases/{case_id}/documents",
    summary="List all document records and versions for a verification case",
)
async def list_case_documents(
    case_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    """
    Retrieve document version history for a case.
    Numbers are masked; storage references remain server-side.
    """
    has_access = await verify_case_access(conn, case_id, current_user, action="view")
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view documents for this case",
        )

    rows = await conn.fetch(
        """
        SELECT id, case_id, case_type, doc_type, version, doc_number_masked,
               issued_by, valid_to, review_status, reviewer_comment,
               uploaded_by, uploaded_at, reviewed_by, reviewed_at
        FROM verification_documents
        WHERE case_id = $1
        ORDER BY doc_type, version DESC
        """,
        case_id,
    )

    results = []
    for r in rows:
        item = dict(r)
        item["id"] = str(item["id"])
        item["case_id"] = str(item["case_id"])
        if item["uploaded_by"]:
            item["uploaded_by"] = str(item["uploaded_by"])
        if item["reviewed_by"]:
            item["reviewed_by"] = str(item["reviewed_by"])
        if item["valid_to"]:
            item["valid_to"] = item["valid_to"].isoformat()
        if item["uploaded_at"]:
            item["uploaded_at"] = item["uploaded_at"].isoformat()
        if item["reviewed_at"]:
            item["reviewed_at"] = item["reviewed_at"].isoformat()
        results.append(item)

    return results

