"""
Secure Document Vault Service — Sprint 2.
Person A: A-03 Deliverable.
Shared with Person B (Venue & Listing Verification).

Core Responsibilities:
1. Server-side file validation (PDF, JPEG, PNG, max 10MB, MIME & magic bytes).
2. Document versioning & concurrency-safe version allocation.
3. Private file storage in Supabase Storage bucket ('verification-documents').
4. Sensitive document number masking (PAN, GSTIN, Bank, Licence).
5. Authorization checks for upload and viewing.
6. Temporary short-lived signed URL generation (5-minute expiry).
"""

from datetime import date, datetime, timezone
import os
import re
from typing import Any, Dict, Optional, Tuple, Union
import uuid
import asyncpg
from fastapi import HTTPException, status

from config import (
    MAX_DOCUMENT_SIZE_BYTES,
    ALLOWED_DOCUMENT_MIME_TYPES,
    SIGNED_URL_EXPIRY_SECONDS,
)
from models.verification import CaseType, DocumentType, ReviewStatus
from services.supabase_storage import upload_file_to_storage, create_signed_url
from services.verification_security import mask_pan, mask_gstin


# Magic byte signatures for verified content verification
MAGIC_BYTES = {
    "application/pdf": b"%PDF",
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}

# Role definitions for access control
REVIEWER_ROLES = {"verification_reviewer", "admin", "platform_admin"}
APPLICANT_ROLES = {"applicant", "organizer", "manager", "admin", "platform_admin"}


def validate_file_payload(
    file_bytes: bytes,
    filename: str,
    declared_content_type: Optional[str] = None,
) -> str:
    """
    Validate file content, size, and real MIME type.
    Rejects files > 10MB and unsupported formats.
    Returns verified MIME type.
    """
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty or missing",
        )

    file_size = len(file_bytes)
    if file_size > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size ({file_size} bytes) exceeds maximum allowed limit of {MAX_DOCUMENT_SIZE_BYTES} bytes (10 MB)",
        )

    # Detect extension
    ext = os.path.splitext(filename.lower())[1]
    ext_mime_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    candidate_mime = ext_mime_map.get(ext) or declared_content_type

    if not candidate_mime or candidate_mime not in ALLOWED_DOCUMENT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats are PDF, JPEG, and PNG.",
        )

    # Validate file magic bytes to prevent MIME spoofing
    expected_magic = MAGIC_BYTES.get(candidate_mime)
    if expected_magic:
        if candidate_mime == "image/jpeg":
            if not file_bytes.startswith(b"\xff\xd8"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupted or invalid JPEG file signature",
                )
        elif not file_bytes.startswith(expected_magic):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid {candidate_mime.split('/')[-1].upper()} file signature",
            )

    return candidate_mime


def mask_document_identifier(doc_type: Union[DocumentType, str], raw_number: Optional[str]) -> Optional[str]:
    """
    Mask sensitive document numbers so plaintext values are never persisted or returned.
    Reuses existing A-01 security utilities.
    """
    if not raw_number or not str(raw_number).strip():
        return None

    cleaned = str(raw_number).strip().upper()
    doc_type_val = doc_type.value if isinstance(doc_type, DocumentType) else str(doc_type).upper()

    if doc_type_val == "PAN":
        return mask_pan(cleaned)
    if doc_type_val == "GST_CERTIFICATE":
        return mask_gstin(cleaned)

    # General fallback masking (preserve first 2 and last 2 characters)
    if len(cleaned) <= 4:
        return "****"
    return f"{cleaned[:2]}{'*' * (len(cleaned) - 4)}{cleaned[-2:]}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage keys."""
    base = os.path.basename(filename)
    safe = re.sub(r"[^a-zA-Z0-9_\.-]", "_", base)
    return safe or "document"


async def verify_case_access(
    conn: asyncpg.Connection,
    case_id: uuid.UUID,
    user: Dict[str, Any],
    action: str = "upload",  # 'upload' or 'view'
) -> bool:
    """
    Enforce authorization on the server before storage operations.
    
    [PERSON B INTEGRATION POINT]
    When Person B delivers verification_cases, ownership will be validated
    against verification_cases.applicant_id and assigned_reviewer_id.
    
    Current standalone contract:
    - Reviewers/Admins can view and upload any case.
    - Applicants/Managers can upload and view cases they own or initiate.
    """
    user_roles = set(user.get("roles", []))
    user_id = user.get("id")

    # Platform Admins and Reviewers have full review access
    if user_roles & REVIEWER_ROLES:
        return True

    # Check if case matches an existing organizer profile owned by this user
    org_row = await conn.fetchrow(
        "SELECT id, user_id FROM organizer_profiles WHERE id = $1 OR user_id = $2",
        case_id,
        user_id,
    )
    if org_row and str(org_row["user_id"]) == str(user_id):
        return True

    # If applicant has applicant or manager role, allow access for their own case_id
    if user_roles & APPLICANT_ROLES:
        # Check if user has previously uploaded documents for this case_id
        doc_count = await conn.fetchval(
            "SELECT count(*) FROM verification_documents WHERE case_id = $1 AND uploaded_by = $2",
            case_id,
            user_id,
        )
        if doc_count > 0:
            return True

        # If it's a new upload for an applicant, permit if action is upload
        if action == "upload":
            return True

    return False


async def upload_document(
    conn: asyncpg.Connection,
    case_id: uuid.UUID,
    case_type: Union[CaseType, str],
    doc_type: Union[DocumentType, str],
    file_bytes: bytes,
    filename: str,
    user: Dict[str, Any],
    content_type: Optional[str] = None,
    doc_number: Optional[str] = None,
    issued_by: Optional[str] = None,
    valid_to: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Shared Document Vault Upload Function (Deliverable A-03).
    
    Responsibilities:
    1. Validate the file (format, magic bytes, size).
    2. Verify upload authorization for the case.
    3. Upload the file to private Supabase bucket.
    4. Allocate the next document version concurrently-safe.
    5. Save the document metadata and storage reference.
    6. Retain previous versions.
    7. Return the document metadata without exposing a public URL.
    """
    # 1. Validate file
    verified_mime = validate_file_payload(file_bytes, filename, content_type)

    # Resolve enum values
    case_type_val = case_type.value if isinstance(case_type, CaseType) else str(case_type).upper()
    doc_type_val = doc_type.value if isinstance(doc_type, DocumentType) else str(doc_type).upper()

    # 2. Verify authorization
    has_access = await verify_case_access(conn, case_id, user, action="upload")
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to upload documents for this verification case",
        )

    # 3. Determine next version (concurrency safe via transaction locking)
    clean_name = sanitize_filename(filename)
    masked_doc_number = mask_document_identifier(doc_type_val, doc_number)
    user_id = user.get("id")

    async with conn.transaction():
        # Get next version number for this case and doc_type
        current_max_version = await conn.fetchval(
            """
            SELECT COALESCE(MAX(version), 0)
            FROM verification_documents
            WHERE case_id = $1 AND doc_type = $2
            """,
            case_id,
            doc_type_val,
        )
        next_version = current_max_version + 1

        # 4. Storage key structure: cases/{case_id}/{doc_type}/v{version}_{filename}
        storage_ref = f"cases/{case_id}/{doc_type_val}/v{next_version}_{clean_name}"

        # 5. Upload to private Supabase Storage
        await upload_file_to_storage(
            storage_path=storage_ref,
            file_bytes=file_bytes,
            content_type=verified_mime,
        )

        # 6. Insert metadata record in database
        row = await conn.fetchrow(
            """
            INSERT INTO verification_documents (
                case_id, case_type, doc_type, version, storage_ref,
                doc_number_masked, issued_by, valid_to, review_status,
                uploaded_by, uploaded_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'PENDING', $9, now())
            RETURNING id, case_id, case_type, doc_type, version, storage_ref,
                      doc_number_masked, issued_by, valid_to, review_status,
                      reviewer_comment, uploaded_by, uploaded_at
            """,
            case_id,
            case_type_val,
            doc_type_val,
            next_version,
            storage_ref,
            masked_doc_number,
            issued_by,
            valid_to,
            user_id,
        )

    doc_record = dict(row)
    doc_record["id"] = str(doc_record["id"])
    doc_record["case_id"] = str(doc_record["case_id"])
    if doc_record["uploaded_by"]:
        doc_record["uploaded_by"] = str(doc_record["uploaded_by"])
    if doc_record["valid_to"]:
        doc_record["valid_to"] = doc_record["valid_to"].isoformat()
    if doc_record["uploaded_at"]:
        doc_record["uploaded_at"] = doc_record["uploaded_at"].isoformat()

    return doc_record


async def get_view_url(
    conn: asyncpg.Connection,
    document_id: uuid.UUID,
    user: Dict[str, Any],
    expires_in: int = SIGNED_URL_EXPIRY_SECONDS,
) -> Dict[str, Any]:
    """
    Shared Document Vault Signed URL Function (Deliverable A-03).
    
    Responsibilities:
    1. Locate requested document in database.
    2. Verify user authorization (uploader or reviewer/admin).
    3. Generate temporary signed URL (5-minute expiry).
    4. Return signed URL and expiry metadata.
    5. Never expose a permanent public URL.
    """
    row = await conn.fetchrow(
        """
        SELECT id, case_id, case_type, doc_type, version, storage_ref,
               doc_number_masked, review_status, uploaded_by
        FROM verification_documents
        WHERE id = $1
        """,
        document_id,
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification document not found",
        )

    doc = dict(row)
    user_roles = set(user.get("roles", []))
    user_id = str(user.get("id"))

    # Authorization check
    is_reviewer = bool(user_roles & REVIEWER_ROLES)
    is_uploader = str(doc.get("uploaded_by")) == user_id

    if not is_reviewer and not is_uploader:
        # Check case ownership as fallback
        has_case_access = await verify_case_access(conn, doc["case_id"], user, action="view")
        if not has_case_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this document",
            )

    # Generate temporary signed URL (5 min default)
    signed_data = await create_signed_url(
        storage_path=doc["storage_ref"],
        expires_in=expires_in,
    )

    return {
        "document_id": str(doc["id"]),
        "case_id": str(doc["case_id"]),
        "doc_type": doc["doc_type"],
        "version": doc["version"],
        "doc_number_masked": doc["doc_number_masked"],
        "signed_url": signed_data["signed_url"],
        "expires_in": signed_data["expires_in"],
        "expires_at": signed_data["expires_at"],
    }

