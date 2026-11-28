# State Machine Diagram: Venue Verification Lifecycle

## 1. Description and Purpose
This diagram models the verification lifecycle of physical event spaces and auditoriums (`venue_verification_cases`). Allowed statuses derive from migrations 0006 and 0007: `draft`, `submitted`, `in_review`, `changes_requested`, `approved`, `rejected`, and `expired`.

## 2. State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> draft: Venue manager initiates verification application

    state draft {
        [*] --> configure_details: Fill seating capacity & layout
        configure_details --> upload_safety_proofs: Attach fire cert & municipal license
    }

    draft --> submitted: Manager clicks submit [proofs uploaded] / append venue_verification_audit
    
    submitted --> in_review: Admin claims case from queue / assign admin_id, append audit
    
    in_review --> changes_requested: Admin flags document or architectural issue / record notes
    changes_requested --> submitted: Manager uploads revised certificates & re-submits

    in_review --> approved: Admin confirms compliance / update venues.verification_status='verified'
    in_review --> rejected: Admin denies approval / record rejection notes

    draft --> expired: Stale application untouched
    submitted --> expired: Administrative queue timeout

    approved --> [*]: Terminal state (shows can be scheduled and published)
    rejected --> [*]: Terminal state (shows blocked at this venue)
    expired --> [*]: Terminal state (must create new draft)
```

## 3. Transition Rules and Constraints
- **Separation:** Independent from the organizer's legal verification. A verified organizer cannot publish shows at an unverified venue.
- **Audit Requirement:** The `venue_verification_audit` table enforces strict event recording for every status transition.
- **Database Column:** Status is lowercase text with check constraint `CHECK (status IN ('draft', 'submitted', 'in_review', 'approved', 'rejected', 'changes_requested', 'expired'))`.
