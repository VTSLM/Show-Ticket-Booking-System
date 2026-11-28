# Sequence Diagram: Venue Verification Flow

## 1. Description and Purpose
This sequence diagram models the Venue Verification process (`backend/routers/venue_verification.py`), which validates physical venue premises, structural capacity declarations, municipal permissions, and safety certifications before shows can be published.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Manager as Venue Manager
    actor Admin as System Administrator
    participant NextJS as Next.js Frontend
    participant VenueVerifyCtrl as venue_verification.py
    participant DB as PostgreSQL 16
    participant Storage as Supabase Storage

    %% 1. Application Creation & Document Upload
    Manager ->> NextJS: Open /venue-verification, select Venue
    NextJS ->> VenueVerifyCtrl: PUT /api/venue-verification/{case_id} {capacity_declared: 1500, emergency_exits: 6}
    VenueVerifyCtrl ->> DB: UPDATE venue_verification_cases SET draft details WHERE manager_id=$manager
    DB -->> VenueVerifyCtrl: Case updated

    Manager ->> NextJS: Upload Fire Safety Certificate (PDF)
    NextJS ->> VenueVerifyCtrl: POST /api/venue-verification/{case_id}/documents (Multipart File)
    VenueVerifyCtrl ->> Storage: Upload to Supabase bucket 'venue-documents'
    Storage -->> VenueVerifyCtrl: storage_path
    VenueVerifyCtrl ->> DB: INSERT INTO venue_case_documents (case_id, document_type='fire_safety', storage_path, verified=false)
    VenueVerifyCtrl -->> NextJS: 200 OK (Document Attached)

    %% 2. Application Submission
    Manager ->> NextJS: Click "Submit for Verification"
    NextJS ->> VenueVerifyCtrl: POST /api/venue-verification/{case_id}/submit
    VenueVerifyCtrl ->> DB: UPDATE venue_verification_cases SET status='submitted' WHERE status IN ('draft', 'changes_requested')
    VenueVerifyCtrl ->> DB: INSERT INTO venue_verification_audit (case_id, action='submitted')
    VenueVerifyCtrl -->> NextJS: 200 OK (Submitted)

    %% 3. Admin Queue & Claiming
    Admin ->> NextJS: Open /admin/venue-reviews
    NextJS ->> VenueVerifyCtrl: GET /api/venue-verification/admin/queue
    VenueVerifyCtrl ->> DB: Fetch cases WHERE status = 'submitted'
    DB -->> VenueVerifyCtrl: List of pending venue cases
    VenueVerifyCtrl -->> NextJS: Render queue

    Admin ->> NextJS: Click "Claim Case"
    NextJS ->> VenueVerifyCtrl: POST /api/venue-verification/admin/{case_id}/claim
    VenueVerifyCtrl ->> DB: UPDATE venue_verification_cases SET status='in_review', assigned_admin_id=$admin WHERE status='submitted'
    VenueVerifyCtrl ->> DB: INSERT INTO venue_verification_audit (case_id, admin_id, action='claimed')

    %% 4. Admin Decision & Audit
    Admin ->> NextJS: Review documents & Click "Approve Venue"
    NextJS ->> VenueVerifyCtrl: POST /api/venue-verification/admin/{case_id}/decision {decision: 'approve', notes: 'Compliance met'}
    VenueVerifyCtrl ->> DB: UPDATE venue_verification_cases SET status='approved', decision='approve', decision_notes=$notes
    VenueVerifyCtrl ->> DB: UPDATE venues SET verification_status='verified' WHERE id = case.venue_id
    VenueVerifyCtrl ->> DB: INSERT INTO venue_verification_audit (case_id, admin_id, action='approved', notes=$notes)
    VenueVerifyCtrl -->> NextJS: 200 OK {status: "approved"}
    NextJS -->> Admin: Success message
```

## 3. Important Implementation Notes
- **Independent Case Lifecycle:** Venue verification is governed independently from organizer verification. An organizer with an approved KYC may still have an unverified venue until physical safety inspections and license certificates are cleared.
- **Audit Non-Repudiation:** Every action (`submitted`, `claimed`, `approved`, `rejected`, `changes_requested`) appends an immutable entry to `venue_verification_audit`.
