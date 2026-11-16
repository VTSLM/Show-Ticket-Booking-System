-- TicketFlow — Customer Care (Sprint 2)
-- Run in the Supabase SQL editor AFTER unified_schema.sql.
-- Safe to run more than once.
--
-- support_requests  : one row per customer problem ("support request")
-- support_messages  : the conversation inside a request (customer + admin replies)
--
-- Note: the existing `tickets` table is for SHOW tickets (QR codes),
--       so customer-care items are called "support requests" to avoid confusion.

CREATE TABLE IF NOT EXISTS support_requests (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_number  varchar(30) NOT NULL UNIQUE,              -- e.g. SR-20261108-4F2A9C
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    booking_id      uuid REFERENCES bookings(id) ON DELETE SET NULL,
    category        varchar(20) NOT NULL
                        CHECK (category IN ('payment','booking','refund','account','other')),
    subject         varchar(150) NOT NULL,
    status          varchar(20) NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','in_progress','resolved','closed')),
    priority        varchar(10) NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('low','normal','high')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz
);

CREATE INDEX IF NOT EXISTS idx_support_requests_user_id ON support_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_support_requests_status  ON support_requests(status);

CREATE TABLE IF NOT EXISTS support_messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      uuid NOT NULL REFERENCES support_requests(id) ON DELETE CASCADE,
    sender_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_admin        boolean NOT NULL DEFAULT false,
    message         text NOT NULL CHECK (length(trim(message)) > 0),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_support_messages_request_id ON support_messages(request_id);

-- Row Level Security: block Supabase's public REST API from these tables
-- (same as bookings/payments). The backend connects directly and is not affected.
ALTER TABLE support_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_messages ENABLE ROW LEVEL SECURITY;
