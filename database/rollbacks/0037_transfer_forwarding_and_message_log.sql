DROP TRIGGER IF EXISTS trg_queue_transfer_messages ON public.notifications;
DROP FUNCTION IF EXISTS public.queue_transfer_messages();
DROP TABLE IF EXISTS public.transfer_message_deliveries;
DROP INDEX IF EXISTS public.idx_ticket_transfers_parent;
ALTER TABLE public.ticket_transfer_seats DROP COLUMN IF EXISTS released_at;
ALTER TABLE public.ticket_transfers DROP CONSTRAINT IF EXISTS chk_ticket_transfers_parent_not_self;
ALTER TABLE public.ticket_transfers DROP COLUMN IF EXISTS parent_transfer_id;
