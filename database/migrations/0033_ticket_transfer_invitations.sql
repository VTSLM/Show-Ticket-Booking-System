-- A pending invitation has no recipient account until its verified email is claimed.
ALTER TABLE public.ticket_transfers ALTER COLUMN to_user_id DROP NOT NULL;
ALTER TABLE public.ticket_transfers ADD CONSTRAINT ticket_transfers_recipient_required
    CHECK (status <> 'accepted' OR to_user_id IS NOT NULL);
