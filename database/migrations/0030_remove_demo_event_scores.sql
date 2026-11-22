-- Every event got made-up scores from 0013 (IMDb 8.2, Metacritic 71, 94% match, age 7+)
-- because they were column defaults. Remove the defaults and clear the scores on events
-- that still carry exactly that demo combination, so no invented numbers are shown (#169).
ALTER TABLE public.events
    ALTER COLUMN imdb_score DROP DEFAULT,
    ALTER COLUMN metacritic_score DROP DEFAULT,
    ALTER COLUMN match_rate DROP DEFAULT,
    ALTER COLUMN age_rating DROP DEFAULT;

UPDATE public.events
   SET imdb_score = NULL, metacritic_score = NULL, match_rate = NULL, age_rating = NULL
 WHERE imdb_score = 8.2 AND metacritic_score = 71 AND match_rate = 94
   AND age_rating IS NOT DISTINCT FROM '7+';
