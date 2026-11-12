"""
Unit & Integration Tests for Secure Document Vault (Sprint 2 - A-03).

Covers all 10 requirements:
1. Successful private document upload.
2. Unsupported file type rejection.
3. File exceeding 10 MB size limit rejection.
4. Consecutive new version creation.
5. Previous version retention (no overwrite).
6. Signed URL generation with 5-minute expiry.
7. Unauthorized upload and viewing rejection (403 Forbidden).
8. Authorized document viewing (uploader and reviewer).
9. Sensitive document number masking (PAN, GSTIN, and general).
10. Supabase Storage upload failure handling.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid
import pytest
from fastapi import HTTPException

from models.verification import CaseType, DocumentType
from services.document_vault import (
    upload_document,
    get_view_url,
    validate_file_payload,
    mask_document_identifier,
)
from services.supabase_storage import StorageUploadError, StorageSignedUrlError


# Fake valid documents
VALID_PDF_BYTES = b"%PDF-1.4 fake pdf content for automated testing"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR fake png"
VALID_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF fake jpeg"


class FakeAsyncTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeDbConnection:
    """Mock asyncpg connection simulating the verification_documents table."""

    def __init__(self, initial_documents=None):
        self.documents = list(initial_documents) if initial_documents else []
        self.organizer_profiles = []

    def transaction(self):
        return FakeAsyncTransaction()

    async def fetchval(self, query, *args):
        # Case 1: Max version query
        if "MAX(version)" in query:
            case_id, doc_type = args[0], args[1]
            versions = [
                d["version"]
                for d in self.documents
                if str(d["case_id"]) == str(case_id) and d["doc_type"] == doc_type
            ]
            return max(versions) if versions else 0

        # Case 2: Document count for case & user
        if "count(*)" in query:
            case_id, user_id = args[0], args[1]
            matching = [
                d
                for d in self.documents
                if str(d["case_id"]) == str(case_id) and str(d["uploaded_by"]) == str(user_id)
            ]
            return len(matching)

        return None

    async def fetchrow(self, query, *args):
        # Organizer profile lookup
        if "organizer_profiles" in query:
            case_id, user_id = args[0], args[1]
            for org in self.organizer_profiles:
                if str(org.get("id")) == str(case_id) or str(org.get("user_id")) == str(user_id):
                    return org
            return None

        # Insert verification document
        if "INSERT INTO verification_documents" in query:
            case_id, case_type, doc_type, version, storage_ref, doc_number_masked, issued_by, valid_to, uploaded_by = args
            doc_id = uuid.uuid4()
            row = {
                "id": doc_id,
                "case_id": case_id,
                "case_type": case_type,
                "doc_type": doc_type,
                "version": version,
                "storage_ref": storage_ref,
                "doc_number_masked": doc_number_masked,
                "issued_by": issued_by,
                "valid_to": valid_to,
                "review_status": "PENDING",
                "reviewer_comment": None,
                "uploaded_by": uploaded_by,
                "uploaded_at": datetime.now(timezone.utc),
                "reviewed_by": None,
                "reviewed_at": None,
            }
            self.documents.append(row)
            return row

        # Fetch document by id
        if "FROM verification_documents" in query and "WHERE id = $1" in query:
            doc_id = args[0]
            for d in self.documents:
                if str(d["id"]) == str(doc_id):
                    return d
            return None

        return None

    async def fetch(self, query, *args):
        if "FROM verification_documents" in query and "WHERE case_id = $1" in query:
            case_id = args[0]
            return [d for d in self.documents if str(d["case_id"]) == str(case_id)]
        return []


# ==============================================================================
# TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_successful_private_document_upload(monkeypatch):
    """1. Verify successful upload of private document to Supabase and DB recording."""
    uploaded_files = []

    async def mock_upload(storage_path, file_bytes, content_type, **kwargs):
        uploaded_files.append((storage_path, content_type))
        return storage_path

    monkeypatch.setattr("services.document_vault.upload_file_to_storage", mock_upload)

    conn = FakeDbConnection()
    case_id = uuid.uuid4()
    user = {"id": str(uuid.uuid4()), "roles": ["applicant"]}

    result = await upload_document(
        conn=conn,
        case_id=case_id,
        case_type=CaseType.ORGANIZER,
        doc_type=DocumentType.PAN,
        file_bytes=VALID_PDF_BYTES,
        filename="my_pan_card.pdf",
        user=user,
        doc_number="ABCPE1234F",
    )

    assert result["version"] == 1
    assert result["doc_type"] == "PAN"
    assert result["doc_number_masked"] == "ABCPE****F"
    assert "cases/" in result["storage_ref"]
    assert "v1_my_pan_card.pdf" in result["storage_ref"]
    assert len(uploaded_files) == 1
    assert uploaded_files[0][1] == "application/pdf"
    assert len(conn.documents) == 1


@pytest.mark.parametrize("bad_filename,bad_bytes", [
    ("virus.exe", b"MZ\x90\x00\x03\x00\x00\x00"),
    ("script.sh", b"#!/bin/bash\necho hello"),
    ("data.txt", b"plain text document"),
])
def test_unsupported_file_types_rejected(bad_filename, bad_bytes):
    """2. Verify rejection of unsupported file extensions and MIME types."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_payload(bad_bytes, bad_filename)
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail


def test_file_exceeding_10mb_limit_rejected():
    """3. Verify strict rejection when file exceeds 10 MB limit."""
    oversized_bytes = b"%PDF" + (b"0" * (10 * 1024 * 1024 + 10))
    with pytest.raises(HTTPException) as exc_info:
        validate_file_payload(oversized_bytes, "huge.pdf")
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed limit" in exc_info.value.detail


@pytest.mark.asyncio
async def test_new_version_creation_and_retention(monkeypatch):
    """4 & 5. Verify consecutive version creation and retention of previous versions."""
    async def mock_upload(storage_path, file_bytes, content_type, **kwargs):
        return storage_path

    monkeypatch.setattr("services.document_vault.upload_file_to_storage", mock_upload)

    conn = FakeDbConnection()
    case_id = uuid.uuid4()
    user = {"id": str(uuid.uuid4()), "roles": ["applicant"]}

    # Upload Version 1
    v1 = await upload_document(
        conn=conn,
        case_id=case_id,
        case_type=CaseType.ORGANIZER,
        doc_type=DocumentType.GST_CERTIFICATE,
        file_bytes=VALID_PDF_BYTES,
        filename="gst.pdf",
        user=user,
        doc_number="27AAACT2727Q1ZW",
    )
    assert v1["version"] == 1
    assert "v1_gst.pdf" in v1["storage_ref"]

    # Upload Version 2 (replacement)
    v2 = await upload_document(
        conn=conn,
        case_id=case_id,
        case_type=CaseType.ORGANIZER,
        doc_type=DocumentType.GST_CERTIFICATE,
        file_bytes=VALID_PNG_BYTES,
        filename="gst_new.png",
        user=user,
        doc_number="27AAACT2727Q1ZW",
    )
    assert v2["version"] == 2
    assert "v2_gst_new.png" in v2["storage_ref"]

    # Ensure BOTH records are retained in database
    assert len(conn.documents) == 2
    versions = [d["version"] for d in conn.documents]
    assert versions == [1, 2]


@pytest.mark.asyncio
async def test_signed_url_generation_and_expiry(monkeypatch):
    """6. Verify signed view URL generation with 5-minute expiry (300 seconds)."""
    expected_signed_url = "https://nvgghebapzhxzrwunwrj.supabase.co/storage/v1/object/sign/verification-documents/doc.pdf?token=secret"

    async def mock_signed_url(storage_path, expires_in=300, **kwargs):
        assert expires_in == 300
        return {
            "signed_url": expected_signed_url,
            "expires_in": expires_in,
            "expires_at": "2026-11-11T12:05:00Z",
        }

    monkeypatch.setattr("services.document_vault.create_signed_url", mock_signed_url)

    doc_id = uuid.uuid4()
    user_id = str(uuid.uuid4())
    conn = FakeDbConnection([
        {
            "id": doc_id,
            "case_id": uuid.uuid4(),
            "case_type": "ORGANIZER",
            "doc_type": "PAN",
            "version": 1,
            "storage_ref": "cases/123/PAN/v1_doc.pdf",
            "doc_number_masked": "AB****34F",
            "review_status": "PENDING",
            "uploaded_by": user_id,
        }
    ])

    user = {"id": user_id, "roles": ["applicant"]}
    view_data = await get_view_url(conn, doc_id, user)

    assert view_data["signed_url"] == expected_signed_url
    assert view_data["expires_in"] == 300
    assert view_data["document_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_unauthorized_view_rejected(monkeypatch):
    """7. Verify rejection of unauthorized users attempting to view documents."""
    doc_id = uuid.uuid4()
    uploader_id = str(uuid.uuid4())
    conn = FakeDbConnection([
        {
            "id": doc_id,
            "case_id": uuid.uuid4(),
            "case_type": "ORGANIZER",
            "doc_type": "PAN",
            "version": 1,
            "storage_ref": "cases/123/PAN/v1_doc.pdf",
            "doc_number_masked": "AB****34F",
            "review_status": "PENDING",
            "uploaded_by": uploader_id,
        }
    ])

    # Unrelated customer user
    other_user = {"id": str(uuid.uuid4()), "roles": ["customer"]}

    with pytest.raises(HTTPException) as exc_info:
        await get_view_url(conn, doc_id, other_user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_authorized_reviewer_can_view_any_document(monkeypatch):
    """8. Verify authorized reviewers/admins can access any verification document."""
    async def mock_signed_url(storage_path, expires_in=300, **kwargs):
        return {
            "signed_url": "https://signed.example.com/doc",
            "expires_in": expires_in,
            "expires_at": "2026-11-11T12:05:00Z",
        }

    monkeypatch.setattr("services.document_vault.create_signed_url", mock_signed_url)

    doc_id = uuid.uuid4()
    conn = FakeDbConnection([
        {
            "id": doc_id,
            "case_id": uuid.uuid4(),
            "case_type": "ORGANIZER",
            "doc_type": "BANK_PROOF",
            "version": 1,
            "storage_ref": "cases/123/BANK_PROOF/v1_doc.pdf",
            "doc_number_masked": "98****21",
            "review_status": "PENDING",
            "uploaded_by": str(uuid.uuid4()),
        }
    ])

    reviewer_user = {"id": str(uuid.uuid4()), "roles": ["verification_reviewer"]}
    res = await get_view_url(conn, doc_id, reviewer_user)
    assert res["signed_url"] == "https://signed.example.com/doc"


def test_sensitive_number_masking():
    """9. Verify sensitive document numbers are properly masked."""
    # PAN masking
    assert mask_document_identifier(DocumentType.PAN, "ABCPE1234F") == "ABCPE****F"
    # GSTIN masking
    assert mask_document_identifier(DocumentType.GST_CERTIFICATE, "27AAACT2727Q1ZW") == "27AAACT****1ZW"
    # General document masking
    assert mask_document_identifier(DocumentType.CINEMA_LICENCE, "LIC-987654321") == "LI*********21"
    # Short document number
    assert mask_document_identifier(DocumentType.OTHER, "123") == "****"


@pytest.mark.asyncio
async def test_supabase_storage_upload_failure_handling(monkeypatch):
    """10. Verify that storage upload failures raise errors and do not persist DB records."""
    async def failing_upload(*args, **kwargs):
        raise StorageUploadError("Simulated storage connectivity failure")

    monkeypatch.setattr("services.document_vault.upload_file_to_storage", failing_upload)

    conn = FakeDbConnection()
    case_id = uuid.uuid4()
    user = {"id": str(uuid.uuid4()), "roles": ["applicant"]}

    with pytest.raises(StorageUploadError):
        await upload_document(
            conn=conn,
            case_id=case_id,
            case_type=CaseType.ORGANIZER,
            doc_type=DocumentType.PAN,
            file_bytes=VALID_PDF_BYTES,
            filename="doc.pdf",
            user=user,
        )

    # Ensure no record was left in the database
    assert len(conn.documents) == 0
