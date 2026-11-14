-- 006_multi_venue_layouts.sql
-- Multi-Venue Seating and Stage Layouts for Concerts, Theatres, and Cinemas
-- Supports General Admission (GA) standing zones alongside reserved numbered seating.

-- 1. Extend screens with layout metadata
ALTER TABLE screens
ADD COLUMN IF NOT EXISTS layout_type VARCHAR(50) DEFAULT 'cinema',
ADD COLUMN IF NOT EXISTS stage_position VARCHAR(30) DEFAULT 'front';

-- 2. General Admission & Standing Zones table for concerts, festivals, and pass tiers
CREATE TABLE IF NOT EXISTS show_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    show_id UUID NOT NULL REFERENCES shows(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    zone_type VARCHAR(50) NOT NULL DEFAULT 'standing', -- 'standing', 'vip_lounge', 'fan_pit', 'pass'
    total_capacity INT NOT NULL CHECK (total_capacity > 0),
    booked_count INT NOT NULL DEFAULT 0 CHECK (booked_count >= 0),
    locked_count INT NOT NULL DEFAULT 0 CHECK (locked_count >= 0),
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    color_hex VARCHAR(20) DEFAULT '#287cff',
    display_order INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_show_zone_capacity CHECK (booked_count + locked_count <= total_capacity)
);

-- Index for fast lookup by show_id
CREATE INDEX IF NOT EXISTS idx_show_zones_show_id ON show_zones(show_id);

-- 3. Zone Bookings table for unreserved / standing tickets
CREATE TABLE IF NOT EXISTS booking_zones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    zone_id UUID NOT NULL REFERENCES show_zones(id) ON DELETE RESTRICT,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (booking_id, zone_id)
);

CREATE INDEX IF NOT EXISTS idx_booking_zones_booking_id ON booking_zones(booking_id);

