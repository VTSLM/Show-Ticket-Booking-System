# Class Diagram: Organizer and Venue Verification

## 1. Description and Purpose
This diagram models the trust and safety domain of TicketFlow. As mandated by the platform requirements, Organizer Verification (KYC/AML, risk scoring, document vaulting) is partitioned separately from Venue Verification (physical inspection, fire safety certification, architectural capacity compliance).

## 2. Class Diagram
```mermaid
classDiagram
    %% Organizer Verification Domain
    class VerificationCase {
        +UUID id
        +UUID organizer_id
        +OrganizerVerificationStatus status
        +Decimal risk_score
        +String trust_tier
        +DateTime submitted_at
        +DateTime reviewed_at
        +UUID reviewed_by
        +String decision_reason
        +DateTime created_at
        +DateTime updated_at
        +calculateRiskScore() Decimal
        +assignTrustTier() String
    }

    class VerificationDocument {
        +UUID id
        +UUID case_id
        +String document_type
        +String storage_path
        +String original_filename
        +String mime_type
        +BigInt file_size_bytes
        +String sha256_hash
        +String status
        +String rejection_reason
        +DateTime verified_at
        +DateTime created_at
    }

    class DuplicateFingerprint {
        +UUID id
        +UUID case_id
        +String fingerprint_type
        +String fingerprint_hash
        +DateTime created_at
    }

    class TrustTierRule {
        +UUID id
        +String tier_code
        +Decimal min_score
        +Decimal max_payout_amount
        +DateTime created_at
    }

    %% Venue Verification Domain
    class VenueVerificationCase {
        +UUID id
        +UUID venue_id
        +UUID manager_id
        +VenueVerificationStatus status
        +Boolean capacity_verified
        +Boolean safety_certificate_verified
        +UUID assigned_admin_id
        +String decision
        +String decision_notes
        +DateTime created_at
        +DateTime updated_at
    }

    class VenueCaseDocument {
        +UUID id
        +UUID case_id
        +String document_type
        +String storage_path
        +Boolean verified
        +DateTime created_at
    }

    class VenueCompliance {
        +UUID id
        +UUID venue_id
        +Boolean fire_safety_cert
        +Boolean insurance_policy
        +Date valid_until
    }

    class VenueVerificationAudit {
        +UUID id
        +UUID case_id
        +UUID admin_id
        +String action
        +String notes
        +DateTime created_at
    }

    class OrganizerVerificationStatus {
        <<enumeration>>
        DRAFT
        SUBMITTED
        IN_REVIEW
        CHANGES_REQUESTED
        APPROVED
        REJECTED
        SUSPENDED
        EXPIRED
    }

    class VenueVerificationStatus {
        <<enumeration>>
        draft
        submitted
        in_review
        changes_requested
        approved
        rejected
        expired
    }

    %% Relationships
    VerificationCase "1" --> "1" OrganizerVerificationStatus : has status
    VerificationCase "1" *-- "1..*" VerificationDocument : holds (cascade delete)
    VerificationCase "1" *-- "0..*" DuplicateFingerprint : tracks hashes (cascade delete)
    VerificationCase "0..*" -- "1" TrustTierRule : evaluated against

    VenueVerificationCase "1" --> "1" VenueVerificationStatus : has status
    VenueVerificationCase "1" *-- "1..*" VenueCaseDocument : requires proofs (cascade delete)
    VenueVerificationCase "1" *-- "0..*" VenueVerificationAudit : logs reviews (cascade delete)
    VenueVerificationCase "1" o-- "0..1" VenueCompliance : validates
```

## 3. Structural Explanations & Implementation Constraints
- **Separation of Concerns:** Organizer verification validates legal business identity (PAN, GSTIN, Company registration, Bank proof), while Venue verification validates physical venue safety, screen counts, and municipal licenses.
- **Composition Constraints (`*--`):** Both `VerificationDocument` and `VenueCaseDocument` share coincident lifetimes with their respective case entities (`ON DELETE CASCADE`). Deletion of a verification case permanently purges document metadata records from the database.
- **Audit Immutability:** `VenueVerificationAudit` entries are append-only; updates and deletes are prevented to guarantee non-repudiation for administrative actions.

## 4. Source Traceability
- Tables: `verification_cases`, `verification_documents`, `duplicate_fingerprints`, `trust_tier_rules`, `venue_verification_cases`, `venue_case_documents`, `venue_compliance`, `venue_verification_audit`.
- Migrations: `0005_organizer_verification.sql`, `0006_venue_verification.sql`, `0007_venue_verification_cases.sql`, `0008_venue_application_fields.sql`.
- Backend Routers: `backend/routers/organizer_verification.py`, `backend/routers/organizer_admin.py`, `backend/routers/venue_verification.py`, `backend/routers/verification_admin.py`.
- Backend Services: `backend/services/verification.py`, `backend/services/document_vault.py`, `backend/services/risk_assessment.py`, `backend/services/trust_tier_service.py`, `backend/services/venue_review.py`.
