-- Reverses the default change in 0028_formats_for_movies_only.sql. The cleared formats
-- are not restored (they were never meaningful for non-movie events).
ALTER TABLE public.events ALTER COLUMN formats SET DEFAULT ARRAY['2D']::text[];
