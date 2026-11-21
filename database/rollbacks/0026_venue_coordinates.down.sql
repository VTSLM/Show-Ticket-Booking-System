ALTER TABLE public.venues DROP CONSTRAINT IF EXISTS venues_coordinates_check;
ALTER TABLE public.venues DROP COLUMN IF EXISTS latitude;
ALTER TABLE public.venues DROP COLUMN IF EXISTS longitude;
