# Sequence Diagram: Organizer Verification Workflow

## 1. Description and Purpose
This sequence diagram models the multi-stage Organizer Verification (KYC/AML) process. It traces the organizer creating a draft application, uploading corporate identity documents into the Supabase document vault, automated risk assessment scoring, administrator review queue claiming, document inspection, and final approval/rejection.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Organizer as Organizer User
    actor Admin as System Administrator
    participant NextJS as Next.js Frontend
    participant OrgVerifyCtrl as organizer_verification.py
    participant AdminVerifyCtrl as organizer_admin.py
    participant VerifySvc as verification.py
    participant RiskSvc as risk_assessment.py
    participant VaultSvc as document_vault.py
    participant DB as PostgreSQL 16
    participant Storage as Supabase Storage

    %% 1. Application Creation & Document Upload
    Organizer ->> NextJS: Open /verification/organizer
    NextJS ->> OrgVerifyCtrl: GET /api/verification/checklist
    OrgVerifyCtrl -->> NextJS: 200 OK (Required document types: PAN, GSTIN, Bank Proof)

    Organizer ->> NextJS: Fill details & Upload Certificate of Incorporation
    NextJS ->> OrgVerifyCtrl: POST /api/verification/applications {org_name, tax_id, ...}
    OrgVerifyCtrl ->> DB: INSERT INTO verification_cases (organizer_id, status='DRAFT')
    DB -->> OrgVerifyCtrl: case_id
    
    NextJS ->> OrgVerifyCtrl: POST /api/verification/cases/{case_id}/documents (Multipart File)
    OrgVerifyCtrl ->> VaultSvc: store_document(file, case_id)
    VaultSvc ->> VaultSvc: Compute SHA-256 fingerprint & scan MIME
    VaultSvc ->> Storage: Upload encrypted blob to private bucket 'verification-documents'
    Storage -->> VaultSvc: storage_path
    VaultSvc ->> DB: INSERT INTO verification_documents (case_id, document_type, storage_path, sha256_hash, status='PENDING')
    VaultSvc ->> DB: INSERT INTO duplicate_fingerprints (case_id, fingerprint_hash)
    OrgVerifyCtrl -->> NextJS: 200 OK (Document uploaded)

    %% 2. Application Submission
    Organizer ->> NextJS: Click "Submit Application"
    NextJS ->> OrgVerifyCtrl: POST /api/verification/applications/{case_id}/submit
    OrgVerifyCtrl ->> VerifySvc: submit_case(case_id)
    VerifySvc ->> RiskSvc: evaluate_organizer_risk(case_id)
    RiskSvc ->> DB: Check for duplicate documents across existing cases
    RiskSvc ->> RiskSvc: Calculate composite risk_score (0.00 - 100.00)
    RiskSvc -->> VerifySvc: risk_score = 12.5 (Low Risk)
    VerifySvc ->> DB: UPDATE verification_cases SET status='SUBMITTED', risk_score=12.5, submitted_at=NOW()
    OrgVerifyCtrl -->> NextJS: 200 OK (Application Submitted)

    %% 3. Admin Review & Decision
    Admin ->> NextJS: Open /admin/organizers (Review Queue)
    NextJS ->> AdminVerifyCtrl: GET /api/admin/organizers/reviews
    AdminVerifyCtrl ->> DB: Fetch cases WHERE status IN ('SUBMITTED', 'IN_REVIEW') ORDER BY risk_score ASC
    DB -->> AdminVerifyCtrl: Case queue
    AdminVerifyCtrl -->> NextJS: Render queue table

    Admin ->> NextJS: Click "Review Application" -> Claim Case
    NextJS ->> AdminVerifyCtrl: POST /api/admin/organizers/{org_id}/claim
    AdminVerifyCtrl ->> DB: UPDATE verification_cases SET status='IN_REVIEW', reviewed_by=$admin_id WHERE status='SUBMITTED'
    
    Admin ->> NextJS: Inspect Document Proof
    NextJS ->> AdminVerifyCtrl: POST /api/admin/organizers/documents/{doc_id}/review {decision: 'APPROVE'}
    AdminVerifyCtrl ->> DB: UPDATE verification_documents SET status='VERIFIED', verified_at=NOW()

    Admin ->> NextJS: Submit Approval Decision
    NextJS ->> AdminVerifyCtrl: POST /api/admin/organizers/{org_id}/decision {decision: 'APPROVE', reason: 'Valid KYC'}
    AdminVerifyCtrl ->> DB: UPDATE verification_cases SET status='APPROVED', decision_reason='Valid KYC', reviewed_at=NOW()
    AdminVerifyCtrl ->> DB: UPDATE organizer_profiles SET verification_status='VERIFIED', payout_status='ELIGIBLE'
    AdminVerifyCtrl ->> DB: INSERT INTO admin_audit_log (action='manager_approved', details)
    AdminVerifyCtrl -->> NextJS: 200 OK {status: "APPROVED"}
    NextJS -->> Admin: Success toast notification
```

## 3. Important Implementation Notes
- **Duplicate Detection:** During submission, `duplicate_fingerprints` compares the document SHA-256 hash against previously approved organizers to detect fraudulent identity recycling.
- **Role-Based Case Claiming:** An admin must explicitly claim an application before making a decision, setting status to `IN_REVIEW` and populating `reviewed_by` to avoid conflicting parallel audits by multiple administrators.
