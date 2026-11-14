-- 003_concert_theatre_fixtures.sql
-- Seed data for testing multi-venue layouts: Concert Stadium and Theatre Auditorium

DO $$
DECLARE
    v_venue_id UUID;
    v_screen_concert UUID;
    v_screen_theatre UUID;
    v_event_concert UUID;
    v_event_theatre UUID;
    v_show_concert UUID;
    v_show_theatre UUID;
    row_char TEXT;
    seat_idx INT;
BEGIN
    -- 1. Create a Grand Arena / Stadium Venue
    INSERT INTO venues (name, city, address)
    VALUES ('DY Patil Stadium & Arena', 'Mumbai', 'Sector 7, Nerul, Navi Mumbai')
    RETURNING id INTO v_venue_id;

    -- 2. Create Concert Arena Screen with Stage & Standing Pit Layout
    INSERT INTO screens (venue_id, name, capacity, layout_type, stage_position)
    VALUES (v_venue_id, 'Main Concert Arena & Grounds', 500, 'concert', 'front')
    RETURNING id INTO v_screen_concert;

    -- Generate Grandstand Seats (Rows A-C, 10 seats each = 30 numbered seats)
    -- Mark Row A and B as Premium
    FOREACH row_char IN ARRAY ARRAY['A', 'B', 'C'] LOOP
        FOR seat_idx IN 1..10 LOOP
            INSERT INTO seats (screen_id, row_label, seat_number, seat_type)
            VALUES (
                v_screen_concert,
                row_char,
                seat_idx,
                CASE WHEN row_char IN ('A', 'B') THEN 'premium'::seat_type ELSE 'standard'::seat_type END
            )
            ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;

    -- 3. Create Concert Event (Published)
    INSERT INTO events (title, description, event_type, duration_minutes, language, genre, poster_url, status)
    VALUES (
        'Coldplay: Music of the Spheres World Tour',
        'Experience the biggest live concert of the year with state-of-the-art stage visuals, immersive audio, and unreserved Fan Pits.',
        'concert',
        180,
        'English',
        'Rock / Pop',
        'https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?auto=format&fit=crop&w=600&q=80',
        'published'
    )
    RETURNING id INTO v_event_concert;

    -- 4. Create Concert Show
    INSERT INTO shows (event_id, screen_id, start_time, end_time, status)
    VALUES (
        v_event_concert,
        v_screen_concert,
        NOW() + INTERVAL '3 days',
        NOW() + INTERVAL '3 days' + INTERVAL '3 hours',
        'scheduled'
    )
    RETURNING id INTO v_show_concert;

    -- Populate show_seats with tiered pricing (Base 2500, Premium 4500)
    INSERT INTO show_seats (show_id, seat_id, price, status)
    SELECT v_show_concert, s.id,
           CASE WHEN s.seat_type = 'premium' THEN 4500.00 ELSE 2500.00 END,
           'available'
    FROM seats s WHERE s.screen_id = v_screen_concert
    ON CONFLICT DO NOTHING;

    -- 5. Add Concert Standing Zones: Fan Pit & VIP Lounge
    INSERT INTO show_zones (show_id, name, zone_type, total_capacity, booked_count, locked_count, price, color_hex, display_order)
    VALUES
        (v_show_concert, 'VIP Fan Pit (Front of Stage Standing)', 'fan_pit', 350, 42, 8, 8500.00, '#ff0055', 1),
        (v_show_concert, 'Early Bird Standing Lawn', 'standing', 800, 150, 20, 3500.00, '#287cff', 2)
    ON CONFLICT DO NOTHING;

    -- 6. Create Theatre Screen
    INSERT INTO screens (venue_id, name, capacity, layout_type, stage_position)
    VALUES (v_venue_id, 'Royal Proscenium Auditorium', 200, 'theatre', 'front')
    RETURNING id INTO v_screen_theatre;

    FOREACH row_char IN ARRAY ARRAY['A', 'B', 'C', 'D'] LOOP
        FOR seat_idx IN 1..8 LOOP
            INSERT INTO seats (screen_id, row_label, seat_number, seat_type)
            VALUES (
                v_screen_theatre,
                row_char,
                seat_idx,
                CASE WHEN row_char = 'A' THEN 'premium'::seat_type ELSE 'standard'::seat_type END
            )
            ON CONFLICT DO NOTHING;
        END LOOP;
    END LOOP;

    -- 7. Create Theatre Event
    INSERT INTO events (title, description, event_type, duration_minutes, language, genre, poster_url, status)
    VALUES (
        'The Royal Shakespeare Company: Hamlet',
        'A magnificent theatre play on the grand proscenium stage with stalls and dress circle seating.',
        'theatre',
        150,
        'English',
        'Drama / Tragedy',
        'https://images.unsplash.com/photo-1507676184212-d03ab07a01bf?auto=format&fit=crop&w=600&q=80',
        'published'
    )
    RETURNING id INTO v_event_theatre;

    -- 8. Create Theatre Show
    INSERT INTO shows (event_id, screen_id, start_time, end_time, status)
    VALUES (
        v_event_theatre,
        v_screen_theatre,
        NOW() + INTERVAL '5 days',
        NOW() + INTERVAL '5 days' + INTERVAL '2 hours 30 minutes',
        'scheduled'
    )
    RETURNING id INTO v_show_theatre;

    INSERT INTO show_seats (show_id, seat_id, price, status)
    SELECT v_show_theatre, s.id,
           CASE WHEN s.seat_type = 'premium' THEN 1800.00 ELSE 950.00 END,
           'available'
    FROM seats s WHERE s.screen_id = v_screen_theatre
    ON CONFLICT DO NOTHING;

END $$;

