# State Machine Diagram: Ticket Lifecycle

## 1. Description and Purpose
This diagram models the lifecycle of individual admission tickets (`tickets`). The valid states and constraints are governed by PostgreSQL CHECK constraints and gate scanning operations in `backend/routers/tickets.py`.

## 2. State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> valid: Payment verified / generate_tickets_for_booking(), render QR code

    state valid {
        [*] --> active_in_wallet: Available for gate entry or peer-to-peer transfer
        active_in_wallet --> active_in_wallet: P2P transfer pending (transfer lock)
    }

    valid --> used: Scanned at venue gate [status='valid' AND show_time matches] / mark scanned_at
    valid --> cancelled: Booking cancelled / refund processed
    valid --> cancelled: Peer-to-peer transfer accepted / old QR revoked, new ticket issued to recipient

    used --> [*]: Terminal state (patron admitted to auditorium)
    cancelled --> [*]: Terminal state (invalid for gate scanning)
```

## 3. Transition Rules and Constraints
- **`valid` State:** The ticket possesses an active, cryptographically signed QR payload.
- **`used` State:** Triggered by `/api/tickets/scan` or `/api/tickets/bookings/{id}/scan`. Scanning a ticket already marked `used` raises HTTP 400 (`Ticket has already been scanned`).
- **`cancelled` State:** Irrevocable invalidation. Occurs either upon booking cancellation or when a ticket transfer is accepted by a recipient (the sender's original ticket is cancelled and replaced by a newly minted ticket with a fresh QR token).
- Database constraint: `status IN ('valid', 'used', 'cancelled')` in `0003_tickets_receipts_and_birthdate.sql`.
