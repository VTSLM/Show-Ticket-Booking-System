# Class Diagram: Tickets, QR Codes, and Peer-to-Peer Transfers

## 1. Description and Purpose
This diagram models ticket issuance and the peer-to-peer transfer subsystem. TicketFlow supports transferring individual reserved seats or portions of general-admission standing zones by email or phone, complete with optional recipient reimbursement, invitation links, forwarding chains, and verifiable QR codes.

## 2. Class Diagram
```mermaid
classDiagram
    class Ticket {
        +UUID id
        +UUID booking_id
        +UUID show_seat_id
        +String ticket_number
        +String qr_code
        +String pdf_url
        +TicketStatus status
        +DateTime created_at
        +DateTime updated_at
        +isValid() bool
        +markUsed() void
        +markCancelled() void
    }

    class TicketTransfer {
        +UUID id
        +UUID booking_id
        +UUID from_user_id
        +UUID to_user_id
        +String to_email
        +String to_phone
        +TransferStatus status
        +String invitation_token
        +String transfer_type
        +DateTime expires_at
        +DateTime responded_at
        +Boolean requires_reimbursement
        +Decimal reimbursement_amount
        +String reimbursement_status
        +UUID parent_transfer_id
        +DateTime created_at
        +DateTime updated_at
        +isPending() bool
        +isExpired() bool
    }

    class TicketTransferSeat {
        +UUID id
        +UUID transfer_id
        +UUID ticket_id
        +UUID show_seat_id
    }

    class TicketTransferZone {
        +UUID id
        +UUID transfer_id
        +UUID booking_zone_id
        +Integer quantity
    }

    class TransferDemoPayment {
        +UUID id
        +UUID transfer_id
        +UUID user_id
        +Decimal amount
        +String currency
        +String status
        +String transaction_reference
        +String payment_method
        +DateTime created_at
    }

    class TransferMessageDelivery {
        +UUID id
        +UUID transfer_id
        +String recipient_email
        +String recipient_phone
        +String channel
        +String status
        +String error_message
        +DateTime created_at
    }

    class TicketStatus {
        <<enumeration>>
        valid
        used
        cancelled
    }

    class TransferStatus {
        <<enumeration>>
        pending
        accepted
        declined
        cancelled
        expired
    }

    %% Relationships
    Ticket "1" --> "1" TicketStatus : has status
    TicketTransfer "1" --> "1" TransferStatus : has status

    TicketTransfer "1" *-- "0..*" TicketTransferSeat : binds (cascade delete)
    TicketTransfer "1" *-- "0..*" TicketTransferZone : binds (cascade delete)
    Ticket "1" -- "0..*" TicketTransferSeat : transferred in

    TicketTransfer "1" *-- "0..1" TransferDemoPayment : settled via
    TicketTransfer "1" *-- "0..*" TransferMessageDelivery : logs delivery
    TicketTransfer "0..1" <-- "0..*" TicketTransfer : forwards to (parent_transfer_id)
```

## 3. Structural Explanations & Constraints
- **Ticket to Transfer Association:** A ticket exists as a verified entitlement generated upon booking confirmation. During a transfer, `TicketTransferSeat` acts as an association link referencing the transferred `Ticket` (`ON DELETE RESTRICT`) and the `TicketTransfer` (`ON DELETE CASCADE`).
- **Transfer Status Lifecycle:** Enforced by PostgreSQL CHECK constraint `ticket_transfers_status_check`: status must be one of `'pending'`, `'accepted'`, `'declined'`, `'cancelled'`, or `'expired'`.
- **Recipient Identification Flexibility:** Migration `0033` enables transfers to unauthenticated users (`to_user_id` is nullable, but at least one of `to_user_id`, `to_email`, or `to_phone` is mandatory via `ticket_transfers_recipient_required`).
- **Transfer Forwarding (Self-Association):** Migration `0037` allows an accepted transfer to be forwarded to a subsequent recipient via `parent_transfer_id REFERENCES ticket_transfers(id)`, with a constraint preventing direct self-parenting (`parent_transfer_id <> id`).

## 4. Source Traceability
- Tables: `tickets`, `ticket_transfers`, `ticket_transfer_seats`, `ticket_transfer_zones`, `transfer_demo_payments`, `transfer_message_deliveries`.
- Migrations: `0003_tickets_receipts_and_birthdate.sql`, `0031_ticket_transfers.sql` to `0037_transfer_forwarding_and_message_log.sql`.
- Backend Routers: `backend/routers/tickets.py`, `backend/routers/ticket_transfers.py`.
- Backend Services: `backend/services/ticket_service.py`, `backend/services/ticket_transfer.py`, `backend/services/transfer_notifier.py`, `backend/services/transfer_reimbursement.py`.
