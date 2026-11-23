-- Cancel or claim all unassigned invitations before rolling this migration back.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.ticket_transfers WHERE to_user_id IS NULL) THEN
        RAISE EXCEPTION 'Cannot roll back while unclaimed invitations exist';
    END IF;
END $$;
ALTER TABLE public.ticket_transfers DROP CONSTRAINT IF EXISTS ticket_transfers_recipient_required;
ALTER TABLE public.ticket_transfers ALTER COLUMN to_user_id SET NOT NULL;
