-- 0037: forwarding + delivery log for transfer messages.
--  * A receiver can pass accepted seats on: the new transfer points at the one they received
--    (parent_transfer_id) and, when accepted, the old transfer's seat rows get released_at set,
--    so nothing is deleted and the whole chain stays in the database.
--  * Every in-app transfer notification gets one email row and one WhatsApp row here
--    (pending -> sending -> sent / failed / skipped), so delivery is recorded and retried.
ALTER TABLE public.ticket_transfers
    ADD COLUMN IF NOT EXISTS parent_transfer_id uuid REFERENCES public.ticket_transfers(id) ON DELETE CASCADE;
ALTER TABLE public.ticket_transfers DROP CONSTRAINT IF EXISTS chk_ticket_transfers_parent_not_self;
ALTER TABLE public.ticket_transfers
    ADD CONSTRAINT chk_ticket_transfers_parent_not_self CHECK (parent_transfer_id IS NULL OR parent_transfer_id <> id);
ALTER TABLE public.ticket_transfer_seats
    ADD COLUMN IF NOT EXISTS released_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_ticket_transfers_parent
    ON public.ticket_transfers (parent_transfer_id) WHERE parent_transfer_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.transfer_message_deliveries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id uuid NOT NULL REFERENCES public.notifications(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    event_name varchar(100) NOT NULL,
    channel varchar(20) NOT NULL CHECK (channel IN ('email', 'whatsapp')),
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'sent', 'failed', 'skipped')),
    attempts integer NOT NULL DEFAULT 0,
    claimed_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    UNIQUE (notification_id, channel)
);
CREATE INDEX IF NOT EXISTS idx_transfer_deliveries_pending
    ON public.transfer_message_deliveries (created_at) WHERE status = 'pending';
ALTER TABLE public.transfer_message_deliveries ENABLE ROW LEVEL SECURITY;

-- Any "transfer.*" notification (received, accepted, declined, cancelled, expired,
-- forwarded, payment_*) automatically queues its email + WhatsApp messages.
CREATE OR REPLACE FUNCTION public.queue_transfer_messages() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.event_name LIKE 'transfer.%' THEN
        INSERT INTO public.transfer_message_deliveries (notification_id, user_id, event_name, channel)
        VALUES (NEW.id, NEW.user_id, NEW.event_name, 'email'),
               (NEW.id, NEW.user_id, NEW.event_name, 'whatsapp')
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_queue_transfer_messages ON public.notifications;
CREATE TRIGGER trg_queue_transfer_messages AFTER INSERT ON public.notifications
    FOR EACH ROW EXECUTE FUNCTION public.queue_transfer_messages();
