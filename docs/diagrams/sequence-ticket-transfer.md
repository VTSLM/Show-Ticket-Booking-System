# Sequence Diagram: Ticket Transfer Flow

## 1. Description and Purpose
This sequence diagram models the peer-to-peer ticket transfer workflow implemented across migrations 0031–0037, `ticket_transfers.py`, and `ticket_transfer.py`. It details the sender initiating a transfer for specific seats or standing zones, recipient invitation via email/token, optional reimbursement via demo checkout, acceptance, and ticket reissuance.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Sender as Ticket Owner (Sender)
    actor Recipient as Recipient User
    participant NextJS as Next.js Frontend
    participant TransferCtrl as ticket_transfers.py
    participant TransferSvc as ticket_transfer.py
    participant NotifierSvc as transfer_notifier.py
    participant DB as PostgreSQL 16
    participant SMTP as Gmail SMTP Server

    %% 1. Sender Initiates Transfer
    Sender ->> NextJS: Open /tickets, select seats, enter recipient email
    NextJS ->> TransferCtrl: POST /api/transfers {booking_id, seat_ids: ["S1"], to_email: "friend@example.com", requires_reimbursement: false}
    TransferCtrl ->> TransferSvc: initiate_transfer(current_user, data)
    TransferSvc ->> DB: Validate sender owns booking and seats, tickets are 'valid'
    TransferSvc ->> DB: Generate secure invitation_token (UUID/random)
    TransferSvc ->> DB: INSERT INTO ticket_transfers (status='pending', expires_at=NOW()+48h, invitation_token)
    TransferSvc ->> DB: INSERT INTO ticket_transfer_seats (transfer_id, ticket_id, show_seat_id)
    DB -->> TransferSvc: Transfer created (transfer_id, token)

    TransferSvc ->> NotifierSvc: dispatch_invitation(transfer_id)
    NotifierSvc ->> DB: INSERT INTO transfer_message_deliveries (channel='email', status='sent')
    NotifierSvc ->> SMTP: Send invitation email with claim link (/tickets/received?token=xyz)
    SMTP -->> Recipient: Deliver transfer email with claim button

    TransferCtrl -->> NextJS: 200 OK {transfer_id, status: "pending", invitation_url}
    NextJS -->> Sender: Display "Transfer Pending" badge in ticket card

    %% 2. Recipient Receives and Claims Transfer
    Recipient ->> NextJS: Clicks link, opens /tickets/received?token=xyz
    NextJS ->> TransferCtrl: GET /api/transfers/received?token=xyz
    TransferCtrl ->> DB: Fetch transfer record, show info, seat numbers
    DB -->> TransferCtrl: Transfer metadata (status='pending', expires_at > NOW())
    TransferCtrl -->> NextJS: 200 OK (Transfer details for confirmation)
    NextJS -->> Recipient: Render ReceivedTicketList confirmation view

    %% 3. Acceptance Flow
    Recipient ->> NextJS: Click "Accept Transfer"
    NextJS ->> TransferCtrl: POST /api/transfers/{transfer_id}/accept
    TransferCtrl ->> TransferSvc: accept_transfer(transfer_id, recipient_user)
    
    TransferSvc ->> DB: BEGIN TRANSACTION
    TransferSvc ->> DB: Lock ticket_transfer row (status='pending' FOR UPDATE)
    TransferSvc ->> DB: UPDATE ticket_transfers SET status='accepted', to_user_id=$recipient, responded_at=NOW()
    TransferSvc ->> DB: Invalidate sender's old tickets (UPDATE tickets SET status='cancelled')
    TransferSvc ->> DB: Generate new tickets for recipient (INSERT INTO tickets with new QR tokens)
    TransferSvc ->> DB: COMMIT TRANSACTION

    TransferSvc ->> NotifierSvc: notify_transfer_accepted(transfer_id)
    NotifierSvc ->> DB: INSERT INTO notifications for Sender ("Transfer Accepted")
    NotifierSvc ->> SMTP: Send confirmation email to both Sender & Recipient
    SMTP -->> Sender: Email: "Your ticket for Seat S1 was accepted"
    SMTP -->> Recipient: Email: "Here is your new Ticket & QR code"

    TransferCtrl -->> NextJS: 200 OK {status: "accepted", ticket_ids: [...]}
    NextJS -->> Recipient: Redirect to /tickets (Ticket now displayed in recipient wallet)
```

## 3. Important Implementation Notes
- **Ticket Revocation & Reissuance:** When a transfer is accepted, the original ticket QR code is permanently invalidated (`status = 'cancelled'`) and a fresh ticket with a new unique QR payload is generated for the recipient. This prevents the original owner from using a printed or screenshotted copy at the gate.
- **Expiration Task:** Background reconciliation runs periodically via `expire_pending_transfers(conn)` in `backend/main.py` to expire unaccepted transfers past their `expires_at` deadline and release the transfer lock.
