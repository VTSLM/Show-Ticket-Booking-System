# State Machine Diagram: Organizer Verification Lifecycle

## 1. Description and Purpose
This diagram models the lifecycle of organizer KYC/AML verification applications (`verification_cases`). Allowed states reflect database migration 0005: `DRAFT`, `SUBMITTED`, `IN_REVIEW`, `CHANGES_REQUESTED`, `APPROVED`, `REJECTED`, `SUSPENDED`, and `EXPIRED`.

## 2. State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> DRAFT: Organizer creates verification application

    state DRAFT {
        [*] --> editing_profile: Fill corporate details
        editing_profile --> uploading_documents: Attach PAN, GSTIN, Bank proof
        uploading_documents --> uploading_documents: Vault encrypted file, compute SHA-256
    }

    DRAFT --> SUBMITTED: Organizer submits application [all mandatory docs uploaded] / compute risk_score, log timestamp
    
    SUBMITTED --> IN_REVIEW: Administrator claims case from review queue / set reviewed_by = admin_id
    
    IN_REVIEW --> CHANGES_REQUESTED: Admin requests document clarification / set decision_reason, notify organizer
    CHANGES_REQUESTED --> SUBMITTED: Organizer re-uploads documents & re-submits

    IN_REVIEW --> APPROVED: Admin approves application / assign trust_tier, enable payout eligibility
    IN_REVIEW --> REJECTED: Admin rejects application / record decision_reason, disable organizer publishing

    APPROVED --> SUSPENDED: Administrative freeze [compliance breach or suspicious activity]
    SUSPENDED --> APPROVED: Administrative reactivation after compliance audit

    DRAFT --> EXPIRED: Application inactive past validity window (e.g. 90 days)
    SUBMITTED --> EXPIRED: Case unreviewed past expiration period

    APPROVED --> [*]: Active organizer on platform
    REJECTED --> [*]: Terminal state (organizer barred from publishing)
    EXPIRED --> [*]: Terminal state (organizer must initiate new application)
```

## 3. Transition Rules and Constraints
- **Invariants:** Governed by `verification_cases.status`. Transition to `APPROVED` automatically updates `organizer_profiles.verification_status = 'VERIFIED'` and `payout_status = 'ELIGIBLE'`.
- **Changes Requested Loop:** Enables organizers to resolve blurred or expired documents without forfeiting their application history.
- **Audit Logging:** Every transition from `IN_REVIEW` appends an entry to `admin_audit_log`.
