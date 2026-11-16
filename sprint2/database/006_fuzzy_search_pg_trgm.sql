-- Migration: Enable fuzzy trigram search for BookMyShow-style typo-tolerant search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_events_title_trgm ON events USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_venues_name_trgm ON venues USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_venues_city_trgm ON venues USING gin (city gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_events_genre_trgm ON events USING gin (genre gin_trgm_ops);
