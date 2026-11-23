-- Quantities of standing-zone tickets allocated to a transfer.
CREATE TABLE IF NOT EXISTS public.ticket_transfer_zones (
    transfer_id uuid NOT NULL REFERENCES public.ticket_transfers(id) ON DELETE CASCADE,
    booking_zone_id uuid NOT NULL REFERENCES public.booking_zones(id) ON DELETE CASCADE,
    quantity integer NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (transfer_id, booking_zone_id)
);
CREATE INDEX IF NOT EXISTS idx_ticket_transfer_zones_booking_zone
    ON public.ticket_transfer_zones (booking_zone_id);
ALTER TABLE public.ticket_transfer_zones ENABLE ROW LEVEL SECURITY;
