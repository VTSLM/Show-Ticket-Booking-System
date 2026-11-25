UPDATE public.ticket_transfers SET status = 'cancelled' WHERE status = 'expired';
DROP INDEX IF EXISTS public.idx_ticket_transfers_pending_created;
ALTER TABLE public.ticket_transfers DROP CONSTRAINT IF EXISTS ticket_transfers_status_check;
ALTER TABLE public.ticket_transfers ADD CONSTRAINT ticket_transfers_status_check
    CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled'));
