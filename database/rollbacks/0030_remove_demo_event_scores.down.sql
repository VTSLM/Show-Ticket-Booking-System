-- Restores the column defaults from 0013. The cleared demo scores are not put back.
ALTER TABLE public.events
    ALTER COLUMN imdb_score SET DEFAULT 8.2,
    ALTER COLUMN metacritic_score SET DEFAULT 71,
    ALTER COLUMN match_rate SET DEFAULT 94,
    ALTER COLUMN age_rating SET DEFAULT '7+';
