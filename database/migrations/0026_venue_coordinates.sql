-- 0025: venue coordinates, used by "shows near me" on the browse page.
-- Nullable: a venue without coordinates is placed at the centre of its city
-- (see backend/services/geo_service.py) until scripts/geocode_venues.py fills them in.

ALTER TABLE public.venues
    ADD COLUMN IF NOT EXISTS latitude  double precision,
    ADD COLUMN IF NOT EXISTS longitude double precision;

ALTER TABLE public.venues DROP CONSTRAINT IF EXISTS venues_coordinates_check;
ALTER TABLE public.venues
    ADD CONSTRAINT venues_coordinates_check CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
    );
