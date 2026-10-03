-- 001_initial_schema.sql
-- Supabase/PostgreSQL schema based on the team's ER diagram.
-- NOTE: enum values below are proposed starter values because the diagram
-- names the enum types but does not specify their allowed values.

create extension if not exists pgcrypto;

do $$ begin create type user_status as enum ('active','inactive','blocked'); exception when duplicate_object then null; end $$;
do $$ begin create type seat_type as enum ('standard','premium','accessible'); exception when duplicate_object then null; end $$;
do $$ begin create type show_seat_status as enum ('available','locked','booked','reserved'); exception when duplicate_object then null; end $$;
do $$ begin create type show_status as enum ('scheduled','cancelled','completed'); exception when duplicate_object then null; end $$;
do $$ begin create type event_type as enum ('movie','concert','theatre','other'); exception when duplicate_object then null; end $$;
do $$ begin create type event_status as enum ('draft','published','inactive'); exception when duplicate_object then null; end $$;
do $$ begin create type booking_status as enum ('pending','confirmed','cancelled','expired'); exception when duplicate_object then null; end $$;
do $$ begin create type payment_method as enum ('razorpay'); exception when duplicate_object then null; end $$;
do $$ begin create type payment_status as enum ('created','pending','successful','failed','refunded'); exception when duplicate_object then null; end $$;

create table if not exists roles (
    id uuid primary key default gen_random_uuid(),
    code varchar(50) not null unique,
    name varchar(100) not null
);

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    firebase_uid varchar(255) not null unique,
    name varchar(100) not null,
    email varchar(255) not null unique,
    phone varchar(20),
    status user_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists user_roles (
    user_id uuid not null references users(id) on delete cascade,
    role_id uuid not null references roles(id) on delete restrict,
    assigned_at timestamptz not null default now(),
    primary key (user_id, role_id)
);

create table if not exists venues (
    id uuid primary key default gen_random_uuid(),
    name varchar(200) not null,
    address text,
    city varchar(100) not null,
    state varchar(100),
    pincode varchar(10),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists screens (
    id uuid primary key default gen_random_uuid(),
    venue_id uuid not null references venues(id) on delete cascade,
    name varchar(100) not null,
    capacity integer not null check (capacity > 0),
    created_at timestamptz not null default now(),
    unique (venue_id, name)
);

create table if not exists seats (
    id uuid primary key default gen_random_uuid(),
    screen_id uuid not null references screens(id) on delete cascade,
    row_label varchar(5) not null,
    seat_number integer not null check (seat_number > 0),
    seat_type seat_type not null default 'standard',
    unique (screen_id, row_label, seat_number)
);

create table if not exists events (
    id uuid primary key default gen_random_uuid(),
    title varchar(200) not null,
    description text,
    event_type event_type not null,
    duration_minutes integer check (duration_minutes is null or duration_minutes > 0),
    language varchar(50),
    genre varchar(100),
    poster_url text,
    status event_status not null default 'draft',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists shows (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references events(id) on delete restrict,
    screen_id uuid not null references screens(id) on delete restrict,
    start_time timestamptz not null,
    end_time timestamptz not null,
    status show_status not null default 'scheduled',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (end_time > start_time)
);

create table if not exists show_seats (
    id uuid primary key default gen_random_uuid(),
    show_id uuid not null references shows(id) on delete cascade,
    seat_id uuid not null references seats(id) on delete restrict,
    price numeric(10,2) not null check (price >= 0),
    status show_seat_status not null default 'available',
    locked_until timestamptz,
    locked_by uuid references users(id) on delete set null,
    unique (show_id, seat_id),
    check ((status = 'locked' and locked_until is not null and locked_by is not null)
           or status <> 'locked')
);

create table if not exists bookings (
    id uuid primary key default gen_random_uuid(),
    booking_number varchar(50) not null unique,
    user_id uuid not null references users(id) on delete restrict,
    show_id uuid not null references shows(id) on delete restrict,
    total_amount numeric(10,2) not null check (total_amount >= 0),
    currency varchar(3) not null default 'INR',
    status booking_status not null default 'pending',
    booked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists booking_seats (
    id uuid primary key default gen_random_uuid(),
    booking_id uuid not null references bookings(id) on delete cascade,
    show_seat_id uuid not null references show_seats(id) on delete restrict,
    unit_price numeric(10,2) not null check (unit_price >= 0),
    unique (booking_id, show_seat_id)
);

create table if not exists payments (
    id uuid primary key default gen_random_uuid(),
    booking_id uuid not null references bookings(id) on delete restrict,
    transaction_id varchar(100),
    amount numeric(10,2) not null check (amount >= 0),
    currency varchar(3) not null default 'INR',
    payment_method payment_method not null default 'razorpay',
    status payment_status not null default 'created',
    paid_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists receipts (
    id uuid primary key default gen_random_uuid(),
    receipt_number varchar(50) not null unique,
    payment_id uuid not null unique references payments(id) on delete restrict,
    issued_at timestamptz not null default now(),
    pdf_url text
);

create index if not exists idx_user_roles_role_id on user_roles(role_id);
create index if not exists idx_screens_venue_id on screens(venue_id);
create index if not exists idx_seats_screen_id on seats(screen_id);
create index if not exists idx_shows_event_id on shows(event_id);
create index if not exists idx_shows_screen_id on shows(screen_id);
create index if not exists idx_shows_start_time on shows(start_time);
create index if not exists idx_show_seats_show_id on show_seats(show_id);
create index if not exists idx_show_seats_status on show_seats(show_id,status);
create index if not exists idx_show_seats_locked_until on show_seats(locked_until) where status='locked';
create index if not exists idx_bookings_user_id on bookings(user_id);
create index if not exists idx_bookings_show_id on bookings(show_id);
create index if not exists idx_booking_seats_show_seat_id on booking_seats(show_seat_id);
create index if not exists idx_payments_booking_id on payments(booking_id);

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists trg_users_updated_at on users;
create trigger trg_users_updated_at before update on users for each row execute function set_updated_at();
drop trigger if exists trg_venues_updated_at on venues;
create trigger trg_venues_updated_at before update on venues for each row execute function set_updated_at();
drop trigger if exists trg_events_updated_at on events;
create trigger trg_events_updated_at before update on events for each row execute function set_updated_at();
drop trigger if exists trg_shows_updated_at on shows;
create trigger trg_shows_updated_at before update on shows for each row execute function set_updated_at();
drop trigger if exists trg_bookings_updated_at on bookings;
create trigger trg_bookings_updated_at before update on bookings for each row execute function set_updated_at();

-- Seat Selection support: read the seats for a show.
create or replace function get_show_seat_map(p_show_id uuid)
returns table (
    show_seat_id uuid, seat_id uuid, row_label varchar,
    seat_number integer, seat_type seat_type, price numeric,
    status show_seat_status, locked_until timestamptz
)
language sql security definer set search_path=public
as $$
    select ss.id, s.id, s.row_label, s.seat_number, s.seat_type, ss.price,
           case when ss.status='locked' and ss.locked_until <= now()
                then 'available'::show_seat_status else ss.status end,
           case when ss.status='locked' and ss.locked_until <= now()
                then null else ss.locked_until end
    from show_seats ss
    join seats s on s.id=ss.seat_id
    where ss.show_id=p_show_id
    order by s.row_label,s.seat_number;
$$;

-- Seat Selection support: atomically lock seats for one user.
create or replace function lock_show_seats(
    p_show_id uuid, p_user_id uuid, p_seat_ids uuid[], p_lock_minutes integer default 5
)
returns table (success boolean, message text, locked_count integer, total_amount numeric)
language plpgsql security definer set search_path=public
as $$
declare requested_count integer; available_count integer; calculated_total numeric;
begin
    requested_count := coalesce(array_length(p_seat_ids,1),0);
    if p_lock_minutes <= 0 then
        return query select false,'Lock duration must be positive.',0,0::numeric; return;
    end if;
    if requested_count=0 then
        return query select false,'No seats were selected.',0,0::numeric; return;
    end if;

    select count(*), coalesce(sum(ss.price),0) into available_count,calculated_total
    from show_seats ss
    where ss.show_id=p_show_id and ss.id=any(p_seat_ids)
      and (ss.status='available'
           or (ss.status='locked' and ss.locked_until <= now())
           or (ss.status='locked' and ss.locked_by=p_user_id))
    for update;

    if available_count <> requested_count then
        return query select false,'One or more selected seats are unavailable.',0,0::numeric; return;
    end if;

    update show_seats
    set status='locked',
        locked_until=now()+make_interval(mins=>p_lock_minutes),
        locked_by=p_user_id
    where show_id=p_show_id and id=any(p_seat_ids);

    return query select true,'Seats locked successfully.',requested_count,calculated_total;
end;
$$;

create or replace function release_show_seat_locks(
    p_show_id uuid, p_user_id uuid, p_seat_ids uuid[]
)
returns integer
language plpgsql security definer set search_path=public
as $$
declare released_count integer;
begin
    update show_seats
    set status='available',locked_until=null,locked_by=null
    where show_id=p_show_id and id=any(p_seat_ids)
      and status='locked' and locked_by=p_user_id;
    get diagnostics released_count=row_count;
    return released_count;
end;
$$;

create or replace function release_expired_show_seat_locks()
returns integer
language plpgsql security definer set search_path=public
as $$
declare released_count integer;
begin
    update show_seats
    set status='available',locked_until=null,locked_by=null
    where status='locked' and locked_until <= now();
    get diagnostics released_count=row_count;
    return released_count;
end;
$$;
