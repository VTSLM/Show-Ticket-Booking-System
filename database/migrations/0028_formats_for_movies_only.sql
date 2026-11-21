-- 0028: cinema formats (2D, 3D, IMAX, 4DX) belong to movies only (#168).
-- Every event used to get '2D' by default, so concerts, comedy and theatre showed it.
UPDATE public.events SET formats = '{}' WHERE event_type::text <> 'movie' AND formats <> '{}';
ALTER TABLE public.events ALTER COLUMN formats SET DEFAULT '{}';
