# State Machine Diagram: Ticket Transfer Lifecycle

## 1. Description and Purpose
This diagram models the lifecycle of peer-to-peer ticket transfers (`ticket_transfers`). As enforced by migration 0032 (`ticket_transfers_status_check`), valid statuses are `'pending'`, `'accepted'`, `'declined'`, `'cancelled'`, and `'expired'`.

## 2. State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> pending: Ticket owner initiates transfer / generate invitation_token, set expires_at = NOW() + 48h

    state pending {
        [*] --> awaiting_claim: Invitation dispatched via email
        awaiting_claim --> awaiting_claim: Re-send invitation notification
    }

    pending --> accepted: Recipient accepts transfer [expires_at > NOW()] / transfer ownership, revoke old QR, issue new ticket
    pending --> declined: Recipient explicitly rejects transfer / release transfer hold back to owner
    pending --> cancelled: Sender recalls transfer before recipient acceptance / release transfer hold
    pending --> expired: Expiration timer elapsed [NOW() > expires_at] / background reconciliation releases hold

    accepted --> [*]: Terminal state (new ticket generated for recipient)
    declined --> [*]: Terminal state (original ticket remains with sender)
    cancelled --> [*]: Terminal state (original ticket remains with sender)
    expired --> [*]: Terminal state (original ticket remains with sender)
```

## 3. Transition Rules and Constraints
- **CHECK Constraint:** `status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired')` in `database/migrations/0032_ticket_transfer_expiry.sql`.
- **Atomic Acceptance:** On acceptance, a database transaction validates that the transfer is still `pending` and not expired (`FOR UPDATE`), revokes the sender's ticket (`UPDATE tickets SET status='cancelled'`), and creates the recipient's ticket.
- **Reimbursement Guard:** If `requires_reimbursement = true`, acceptance transitions through demo payment settlement (`reimbursement_status = 'completed'`) before tickets are transferred.
