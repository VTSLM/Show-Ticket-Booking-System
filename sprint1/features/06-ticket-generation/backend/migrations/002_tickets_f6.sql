-- 002_tickets_f6.sql
-- F6 · Digital Ticket Generation & Verification
--
-- Creates a self-contained `tickets` table that stores the full confirmed
-- ticket payload. It is intentionally denormalised for Sprint 1 so that
-- F6 works independently of whether F3/F4/F5 have wired up the full
-- bookings → payments → receipts chain.
--
-- Sprint 2 migration will add a FK to `receipts` once all features merge.

create table if not exists tickets (
    id                uuid        primary key default gen_random_uuid(),

    -- Booking identity (matches the booking_number from the bookings table)
    booking_number    varchar(50) not null unique,
    transaction_id    varchar(100),

    -- Denormalised user snapshot (avoids requiring a users row in Sprint 1)
    user_id_str       varchar(50),
    user_name         varchar(100) not null,
    user_email        varchar(255) not null,

    -- Denormalised event/show snapshot
    event_id_str      varchar(50),
    event_name        varchar(200) not null,
    event_date        varchar(20)  not null,
    event_time        varchar(10)  not null,
    event_venue       text         not null,

    -- Seats as a JSON array: [{seat_id, row, number, tier, price}, …]
    seats             jsonb        not null default '[]',

    total_amount      numeric(10,2) not null check (total_amount >= 0),
    payment_status    varchar(20)   not null default 'SUCCESS',
    booked_at         timestamptz   not null,
    confirmed_at      timestamptz   not null default now(),

    -- QR / entry verification
    is_used           boolean       not null default false,
    used_at           timestamptz,

    -- Optional: Cloudinary PDF URL (populated in Sprint 2 when Cloudinary wired up)
    pdf_url           text,

    check (
        (is_used = false and used_at is null) or
        (is_used = true  and used_at is not null)
    )
);

-- Fast lookup for the verify endpoint
create index if not exists idx_tickets_booking_number on tickets(booking_number);
create index if not exists idx_tickets_user_email     on tickets(user_email);
create index if not exists idx_tickets_is_used        on tickets(is_used) where is_used = false;

-- Convenience view: all unscanned tickets
create or replace view v_active_tickets as
    select * from tickets where is_used = false;

comment on table  tickets                is 'F6: confirmed ticket records with QR scan state';
comment on column tickets.booking_number is 'Matches bookings.booking_number once F5 is wired in';
comment on column tickets.seats          is 'JSON array of {seat_id, row, number, tier, price}';
comment on column tickets.is_used        is 'Set to true on first QR scan at venue entry';
