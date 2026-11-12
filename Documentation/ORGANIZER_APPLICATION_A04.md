# Deliverable A-04: Organizer Verification Application Experience

## 1. Overview
The **Organizer Verification Application Experience (A-04)** delivers the applicant-facing onboarding workflow for TicketFlow organizers. It enables prospective event organizers to create, progressively save, resume, and submit verification applications for administrative approval.

This module integrates:
- **A-01 Foundation:** Relational schema (`organizer_profiles`, `bank_accounts`, `verification_documents`, `notifications`), trust tiers, and cryptographic masking utilities.
- **A-02 Identity Validators:** Real-time format, checksum, and business-entity structural validation for PAN, GSTIN, and settlement bank IFSC.
- **A-03 Secure Document Vault:** Supabase Storage integration with private access controls, concurrency-safe document versioning, and time-bounded (5-minute) signed view URLs.

---

## 2. Architecture & Design Principles

### Application State Machine
Organizers interact with applications through defined lifecycle states:
- `DRAFT`: Active, editable application. The organizer can update profile details, bank accounts, and attach document versions.
- `SUBMITTED`: Locked application under administrative review. Modifications are forbidden.
- `CHANGES_REQUESTED`: Reviewer has requested corrections or replacement documents. The application re-opens for applicant updates and re-submission.

```
       ┌───────────────────────────────┐
       │                               ▼
[New / DRAFT] ───(Submit)───► [SUBMITTED] ───(Reviewer)───► [CHANGES_REQUESTED]
                                       │
                                       └───(Reviewer)───► [APPROVED / REJECTED]
```

### UI / UX Consistency
The frontend interface (`/verification/organizer`) adheres to the dark navy design system (`#070c18` background, `#0b1328` card background, `border-blue-900/60`, `#2563eb` action buttons) established across TicketFlow manager and venue verification workspaces.

---

## 3. Frontend Application Wizard

The application is structured as a 5-step interactive wizard:

1. **Step 1: Business Information**
   - Legal Business Name (required, min 2 chars).
   - Business Type: `INDIVIDUAL`, `SOLE_PROPRIETOR`, `COMPANY`, `LLP`, `TRUST`.
   - Operating State: Selection across 33 Indian States and Union Territories.

2. **Step 2: Identity Credentials**
   - Permanent Account Number (PAN): Real-time client-side validation ensuring the 4th character matches the entity structure (`P` for Individual/Proprietor, `C` for Company, `F` for LLP, `T`/`A` for Trust).
   - GSTIN: Mandatory for Company and LLP entities; validated with state code, embedded PAN, and modulo-36 checksum.

3. **Step 3: Settlement Bank & Payout**
   - Bank Account Holder Name.
   - Bank IFSC: 11-character regex verification.
   - Account Number & Confirmation: Matching validation and tokenized masking.
   - Automatic draft saving upon advancing to Step 4.

4. **Step 4: Verification Documents**
   - Dynamic checklist derived by entity type:
     - `INDIVIDUAL` / `SOLE_PROPRIETOR`: PAN Card, Bank Proof.
     - `COMPANY` / `LLP`: PAN Card, GST Certificate, Bank Proof, Business Registration (COI / MOA).
     - `TRUST`: PAN Card, Bank Proof, Trust Deed / Non-profit Registration.
   - Version retention: Uploading new revisions increments the document version (`v1`, `v2`, etc.) without overwriting previous versions.
   - Signed preview: Instant access to private vault documents using temporary 5-minute signed URLs.

5. **Step 5: Review & Submission**
   - Comprehensive summary table showing masked identifiers (`ABCPE****F`, `********9012`).
   - Document readiness checklist with visual verification badges.
   - Submission gate enforcing completeness before final submission.

---

## 4. REST API Specification

### 1. Document Requirements Checklist
- **Endpoint:** `GET /api/verification/organizer/checklist`
- **Query Parameter:** `business_type` (Enum: `INDIVIDUAL`, `SOLE_PROPRIETOR`, `COMPANY`, `LLP`, `TRUST`)
- **Response:**
  ```json
  {
    "business_type": "COMPANY",
    "required_documents": ["PAN", "GST_CERTIFICATE", "BANK_PROOF", "BUSINESS_REGISTRATION"],
    "optional_documents": ["SIGNATORY_ID", "AUTHORISATION_LETTER", "OTHER"]
  }
  ```

### 2. My Applications
- **Endpoint:** `GET /api/verification/organizer/applications/me`
- **Security:** Requires valid JWT bearer token.
- **Response:** Array of user-owned application profiles with masked bank details and attached document revision history.

### 3. Save or Update Draft
- **Endpoint:** `POST /api/verification/organizer/applications`
- **Request Body:**
  ```json
  {
    "legal_name": "Aarav Productions Pvt Ltd",
    "business_type": "COMPANY",
    "state": "Maharashtra",
    "pan": "AAACC1122C",
    "gstin": "27AAACC1122C1Z5",
    "bank_holder_name": "Aarav Productions Pvt Ltd",
    "ifsc": "HDFC0001234",
    "account_number": "123456789012"
  }
  ```
- **Behavior:** Validates formats, applies salted hash to bank account, applies display masks, and updates or inserts profile records within a database transaction.

### 4. Submit Application
- **Endpoint:** `POST /api/verification/organizer/applications/{application_id}/submit`
- **Validation Gates:**
  1. Profile ownership check (`user_id` matches current authenticated user).
  2. Status check (must be `DRAFT` or `CHANGES_REQUESTED`).
  3. Field completeness (legal name, business type, state, valid PAN, GSTIN for Company/LLP).
  4. Settlement bank account presence.
  5. Required document verification (all mandatory doc types must be present in `verification_documents`).
- **Audit:** Emits `case_submitted` event into `notifications` table.

---

## 5. Security & Privacy Guarantees

1. **Identifier Masking:** Plaintext PAN, GSTIN, and bank account numbers are never persisted in the database or exposed in API responses.
2. **Server-Side Storage Privileges:** All Supabase Storage operations (bucket checks, object uploads, signed URL creation) are executed server-side using service-role authorization. The client never receives storage secret keys.
3. **Strict Ownership Isolation:** API endpoints enforce applicant ownership checks on every read, write, and submission request.
4. **Temporary Document URLs:** Storage objects remain private (`public: false`). URLs generated for viewing expire automatically after 300 seconds (5 minutes).

---

## 6. Test Verification

Automated tests cover all core application flows in `sprint1_v2/backend/tests/test_organizer_application.py`:
- `test_get_document_checklist`
- `test_save_draft_with_pan_and_bank`
- `test_save_draft_pan_validation_failure`
- `test_resume_saved_draft`
- `test_pre_submission_validation_missing_documents`
- `test_successful_application_submission`
- `test_re_edit_on_submitted_application_rejected`

All 102 backend tests across Sprint 2 deliverables (A-01, A-02, A-03, A-04) pass with zero failures.
