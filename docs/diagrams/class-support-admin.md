# Class Diagram: Notifications, Support, and System Administration

## 1. Description and Purpose
This diagram models user notifications, support inquiry ticketing, terms & conditions legal compliance tracking, and administrative audit logging across the TicketFlow system.

## 2. Class Diagram
```mermaid
classDiagram
    class Notification {
        +UUID id
        +UUID user_id
        +String title
        +String message
        +String type
        +Boolean is_read
        +DateTime created_at
        +markAsRead() void
    }

    class SupportRequest {
        +UUID id
        +UUID user_id
        +String subject
        +String category
        +SupportStatus status
        +SupportPriority priority
        +DateTime created_at
        +DateTime updated_at
        +closeRequest() void
        +reopenRequest() void
    }

    class SupportMessage {
        +UUID id
        +UUID request_id
        +UUID sender_id
        +String sender_role
        +String message
        +DateTime created_at
    }

    class AdminAuditLog {
        +UUID id
        +UUID admin_id
        +UUID target_user_id
        +String action
        +JSONB details
        +String reason
        +DateTime created_at
    }

    class AuditLog {
        +UUID id
        +UUID user_id
        +String action
        +String entity_type
        +UUID entity_id
        +JSONB details
        +String ip_address
        +DateTime created_at
    }

    class TermsAcceptance {
        +UUID id
        +UUID user_id
        +UUID booking_id
        +String terms_hash
        +String terms_text
        +String ip_address
        +String user_agent
        +DateTime accepted_at
    }

    class SupportStatus {
        <<enumeration>>
        open
        in_progress
        waiting_on_customer
        resolved
        closed
    }

    class SupportPriority {
        <<enumeration>>
        low
        medium
        high
        urgent
    }

    %% Relationships
    SupportRequest "1" --> "1" SupportStatus : has status
    SupportRequest "1" --> "1" SupportPriority : has priority
    SupportRequest "1" *-- "1..*" SupportMessage : contains conversation (cascade delete)
```

## 3. Structural Explanations & Implementation Constraints
- **Support Request Conversation Hierarchy:** A `SupportRequest` acts as an aggregate container holding ordered `SupportMessage` instances (`request_id REFERENCES support_requests(id) ON DELETE CASCADE`). Messages carry `sender_role` to distinguish customer inquiries from admin responses.
- **Audit Immutability:** Both `AdminAuditLog` and `AuditLog` are append-only. CHECK constraint `admin_audit_log_action_check` validates allowed audit categories: `'role_added'`, `'role_removed'`, `'status_changed'`, `'manager_approved'`, `'manager_rejected'`.
- **Legal Compliance (`TermsAcceptance`):** Records immutable digital acceptance of terms (`terms_hash` SHA-256 fingerprint, user agent, IP address, timestamp) linked to the confirmed booking.

## 4. Source Traceability
- Tables: `notifications`, `support_requests`, `support_messages`, `admin_audit_log`, `audit_log`, `terms_acceptances`.
- Migrations: `0004_customer_care.sql`, `0019_show_details_layout_and_terms.sql`, `0026_admin_audit_log.sql`.
- Backend Routers: `backend/routers/notifications.py`, `backend/routers/support.py`, `backend/routers/support_admin.py`, `backend/routers/admin_users.py`.
- Backend Services: `backend/services/terms_service.py`, `backend/services/support_email_service.py`.
