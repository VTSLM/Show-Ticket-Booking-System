-- 008_show_details_layout_and_terms.sql
-- Show Details Page + Flexible Venue Seat Layout + Show-Specific Terms & Conditions

-- 1. Extend Events table for detailed show pages (cast, crew, artists, formats, certification, release date, terms)
ALTER TABLE events
ADD COLUMN IF NOT EXISTS cast_crew JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS artists JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS formats TEXT[] DEFAULT ARRAY['2D']::text[],
ADD COLUMN IF NOT EXISTS certificate VARCHAR(20) DEFAULT 'UA',
ADD COLUMN IF NOT EXISTS release_date DATE,
ADD COLUMN IF NOT EXISTS terms_and_conditions TEXT;

-- 2. Extend Shows table with show-specific Terms & Conditions
ALTER TABLE shows
ADD COLUMN IF NOT EXISTS terms_and_conditions TEXT;

-- 3. Extend Screens with coordinate layout configuration (dimensions, stage shape, sections, aisles, polygons)
ALTER TABLE screens
ADD COLUMN IF NOT EXISTS layout_config JSONB;

-- 4. Extend Seats with exact visual coordinates (x, y) and section assignment
ALTER TABLE seats
ADD COLUMN IF NOT EXISTS x_pos NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS y_pos NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS section_name VARCHAR(100);

-- 5. Extend Show Zones with coordinate/polygon geometry for flexible visual mapping
ALTER TABLE show_zones
ADD COLUMN IF NOT EXISTS polygon_coords JSONB,
ADD COLUMN IF NOT EXISTS x_pos NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS y_pos NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS width NUMERIC(8,2),
ADD COLUMN IF NOT EXISTS height NUMERIC(8,2);

-- 6. Audit & Acceptance Recording Table for Show-Specific Terms & Conditions
CREATE TABLE IF NOT EXISTS terms_acceptances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    show_id UUID NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    booking_id UUID REFERENCES bookings(id) ON DELETE CASCADE,
    terms_hash VARCHAR(64) NOT NULL,
    terms_text TEXT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_terms_acceptances_user_show ON terms_acceptances(user_id, show_id);
CREATE INDEX IF NOT EXISTS idx_terms_acceptances_booking ON terms_acceptances(booking_id);
