CREATE TABLE IF NOT EXISTS public.transfer_demo_payments (
    transfer_id uuid PRIMARY KEY REFERENCES public.ticket_transfers(id) ON DELETE RESTRICT,
    razorpay_order_id text NOT NULL UNIQUE,
    original_payment_id text NOT NULL,
    amount_paise integer NOT NULL CHECK (amount_paise >= 100),
    recipient_payment_id text UNIQUE,
    refund_target text CHECK (refund_target IN ('buyer', 'recipient')),
    refund_id text UNIQUE,
    refund_status text CHECK (refund_status IN ('pending', 'processed', 'failed')),
    checked_at timestamptz DEFAULT now() NOT NULL
);
ALTER TABLE public.transfer_demo_payments ENABLE ROW LEVEL SECURITY;
