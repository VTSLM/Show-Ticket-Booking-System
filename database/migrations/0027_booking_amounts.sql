-- 0027: price breakdown on bookings (#174).
-- The live database already has these columns (they were added outside the migrations,
-- and bookings failed because the code did not fill subtotal_amount). This brings the
-- repository in line; every step is safe to run on the live database too.
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS subtotal_amount numeric(10,2);
UPDATE public.bookings SET subtotal_amount = total_amount WHERE subtotal_amount IS NULL;
ALTER TABLE public.bookings ALTER COLUMN subtotal_amount SET NOT NULL;

ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS discount_amount numeric(10,2) NOT NULL DEFAULT 0;

-- For the planned coupons feature; the foreign key is added with the coupons table.
ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS coupon_id uuid;
