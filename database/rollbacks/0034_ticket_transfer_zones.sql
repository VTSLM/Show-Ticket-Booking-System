-- Never silently discard standing-ticket allocations on rollback.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM public.ticket_transfer_zones) THEN
        RAISE EXCEPTION 'Cannot roll back while standing-ticket transfers exist';
    END IF;
END $$;
DROP TABLE IF EXISTS public.ticket_transfer_zones;
