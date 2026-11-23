ALTER TABLE public.ticket_transfers
    ADD COLUMN IF NOT EXISTS requested_share_paise integer CHECK (requested_share_paise >= 100);

-- Preserve checkouts already opened before the sender could request payment.
UPDATE public.ticket_transfers tt
SET requested_share_paise = dp.amount_paise
FROM public.transfer_demo_payments dp
WHERE dp.transfer_id = tt.id AND tt.requested_share_paise IS NULL;
