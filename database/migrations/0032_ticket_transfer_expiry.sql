-- Transfers expire after 24 hours or when the show starts.
ALTER TABLE public.ticket_transfers DROP CONSTRAINT IF EXISTS ticket_transfers_status_check;
ALTER TABLE public.ticket_transfers ADD CONSTRAINT ticket_transfers_status_check
    CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled', 'expired'));
CREATE INDEX IF NOT EXISTS idx_ticket_transfers_pending_created
    ON public.ticket_transfers (created_at) WHERE status = 'pending';
