-- Reverses 0031_ticket_transfers.sql. Deletes every ticket transfer, so friends who
-- received seats lose their QR codes.
DROP TABLE IF EXISTS public.ticket_transfer_seats;
DROP TABLE IF EXISTS public.ticket_transfers;
