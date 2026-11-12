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
