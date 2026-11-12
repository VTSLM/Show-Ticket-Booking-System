# Sprint 2 Deliverable A-03: Secure Document Vault

**Project:** TicketFlow – Show Ticket Booking System  
**Sprint:** Sprint 2  
**Role:** Person A — Organizer and Business Verification  
**Deliverable:** A-03 (Secure Document Vault)  
**Status:** COMPLETE  

---

## 1. Executive Summary

Deliverable A-03 implements the private, server-side document storage and retrieval infrastructure for verification cases across TicketFlow:
1. **Private Supabase Storage:** Integrates directly with Supabase Storage REST API using service-role credentials to store document binaries in the private `verification-documents` bucket.
2. **Server-Side File Validation:** Rejects unsupported MIME types and spoofed extensions using magic byte signatures (`%PDF`, JPEG, PNG) and strictly enforces the 10 MB maximum file size limit.
3. **Concurrency-Safe Document Versioning:** Reuses the A-01 `verification_documents` table to record consecutive document revisions (`v1`, `v2`, ...), retaining all previous submissions without overwriting or deleting historical documents.
4. **Temporary Signed View URLs:** Restricts document retrieval to short-lived signed URLs with a 5-minute (300 seconds) expiration window, eliminating permanent public URL exposure.
5. **Sensitive Number Masking:** Automatically masks sensitive identifiers (PAN, GSTIN, licence numbers) before database insertion and API responses.
6. **Person B Integration Foundation:** Provides shared endpoints and functions (`upload_document`, `get_view_url`) compatible with Person B's Venue and Listing Verification requirements.

---

## 2. Storage Architecture & Privacy

All verification documents are held in a private Supabase Storage bucket:
- **Bucket:** `verification-documents` (`public = false`)
- **Key Partitioning:** `cases/{case_id}/{doc_type}/v{version}_{filename}`
- **Immutability:** Storage uploads enforce `x-upsert: false` so that physical file revisions are never overwritten in place.

---

## 3. Server-Side File Validation Matrix

| File Type | Extension | MIME Type | Magic Bytes |
| :--- | :--- | :--- | :--- |
| **PDF** | `.pdf` | `application/pdf` | `%PDF` (`0x25 0x50 0x44 0x46`) |
| **JPEG** | `.jpg`, `.jpeg` | `image/jpeg` | `0xFF 0xD8 0xFF` |
| **PNG** | `.png` | `image/png` | `0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A` |

Any file exceeding 10,485,760 bytes (10 MB) or failing signature matching is rejected with HTTP 400 Bad Request.

---

## 4. REST API Endpoints

| Method | Path | Auth / Role | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/verification/cases/{case_id}/documents` | Applicant / Manager / Admin | Upload new document version |
| `GET` | `/api/verification/documents/{document_id}/view` | Applicant (owner) / Reviewer / Admin | Generate 5-min temporary signed view URL |
| `GET` | `/api/verification/cases/{case_id}/documents` | Applicant (owner) / Reviewer / Admin | List all document versions with masked numbers |

---

## 5. Automated Test Suite

A comprehensive test suite in `sprint1_v2/backend/tests/test_document_vault.py` covers all 10 required scenarios:
1. Successful private document upload.
2. Rejection of unsupported file types (`.exe`, `.sh`, `.txt`).
3. Rejection of files exceeding 10 MB limit.
4. Concurrency-safe version increment (`v1 -> v2`).
5. Retention of previous versions.
6. Signed URL generation with 300-second expiry.
7. Rejection of unauthorized users (HTTP 403 Forbidden).
8. Authorized reviewer and uploader access.
9. Sensitive number masking (PAN, GSTIN, licence).
10. Supabase Storage upload failure handling without orphaned database records.

Total backend test suite status:
```
======================= 95 passed, 10 warnings in 2.64s =======================
```
