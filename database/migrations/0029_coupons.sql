CREATE TABLE IF NOT EXISTS public.coupons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid REFERENCES public.events(id) ON DELETE RESTRICT,
    created_by uuid REFERENCES public.users(id) ON DELETE RESTRICT,
    code varchar(30) NOT NULL,
    discount_percent numeric(5,2) NOT NULL
        CHECK (discount_percent > 0 AND discount_percent < 100),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.coupons
    ALTER COLUMN event_id DROP NOT NULL;

ALTER TABLE public.coupons
    ALTER COLUMN created_by DROP NOT NULL;

ALTER TABLE public.coupons ENABLE ROW LEVEL SECURITY;

CREATE UNIQUE INDEX IF NOT EXISTS idx_coupons_event_code
    ON public.coupons (event_id, lower(code));

CREATE UNIQUE INDEX IF NOT EXISTS idx_coupons_global_code
    ON public.coupons (lower(code))
    WHERE event_id IS NULL;

DO $$
BEGIN
    ALTER TABLE public.bookings
        ADD CONSTRAINT bookings_coupon_id_fkey
        FOREIGN KEY (coupon_id) REFERENCES public.coupons(id)
        ON DELETE RESTRICT;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

INSERT INTO public.coupons (event_id, created_by, code, discount_percent, is_active)
VALUES (NULL, NULL, 'FIRST20', 20.00, true)
ON CONFLICT (lower(code)) WHERE event_id IS NULL
DO UPDATE SET discount_percent = EXCLUDED.discount_percent,
              is_active = true;