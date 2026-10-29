-- Feature 05: Razorpay Test Mode persistence on the shared Supabase/PostgreSQL DB.
-- Apply after sprint1/database/migrations/001_initial_schema.sql.
-- Copy this migration into the team's sprint1/database/migrations folder before merge.

create table if not exists payment_orders (
    id uuid primary key default gen_random_uuid(),
    booking_id uuid not null references bookings(id) on delete restrict,
    razorpay_order_id varchar(100) not null unique,
    amount numeric(10,2) not null check (amount > 0),
    currency varchar(3) not null default 'INR',
    status varchar(32) not null default 'created'
        check (status in ('creating','created','verification_pending','authorized','successful','successful_needs_review','failed','cancelled')),
    created_by uuid not null references users(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table payments add column if not exists payment_order_id uuid references payment_orders(id) on delete restrict;
alter table payments add column if not exists razorpay_payment_id varchar(100);
alter table payments add column if not exists provider_method varchar(32);
alter table payments add column if not exists provider_created_at timestamptz;
alter table payments add column if not exists signature_verified_at timestamptz;
alter table payments add column if not exists failure_reason text;

create unique index if not exists uq_payment_orders_razorpay_order_id on payment_orders(razorpay_order_id);
create unique index if not exists uq_payments_razorpay_payment_id on payments(razorpay_payment_id) where razorpay_payment_id is not null;
create index if not exists idx_payment_orders_booking_created on payment_orders(booking_id, created_at desc);
create index if not exists idx_payments_payment_order_id on payments(payment_order_id);
create index if not exists idx_payment_orders_created_by on payment_orders(created_by);

-- Only one unresolved order per booking. A captured payment requiring manual
-- attention remains blocking until the team reconciles the booking/refund.
create unique index if not exists uq_one_unresolved_payment_order_per_booking
on payment_orders(booking_id)
where status in ('creating','created','verification_pending','authorized','successful_needs_review');

create index if not exists idx_payments_transaction_id on payments(transaction_id);

create or replace function set_payment_order_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists trg_payment_orders_updated_at on payment_orders;
create trigger trg_payment_orders_updated_at before update on payment_orders
for each row execute function set_payment_order_updated_at();

-- Important: after applying, configure RLS/grants according to the project's
-- server-side access model. The FastAPI service should use a server-only DB URL.
-- Do not expose a service-role key or unrestricted DB credentials to the browser.

-- Corrected Seat Selection helper: lock all selected rows first, then aggregate.
-- PostgreSQL cannot combine FOR UPDATE with COUNT/SUM aggregates in a single query.
create or replace function lock_show_seats(
    p_show_id uuid, p_user_id uuid, p_seat_ids uuid[], p_lock_minutes integer default 5
)
returns table (success boolean, message text, locked_count integer, total_amount numeric)
language plpgsql security definer set search_path=pg_catalog, public, pg_temp
as $$
declare
    requested_count integer;
    distinct_count integer;
    available_count integer;
    calculated_total numeric;
begin
    requested_count := coalesce(cardinality(p_seat_ids), 0);
    if p_lock_minutes <= 0 then
        return query select false, 'Lock duration must be positive.', 0, 0::numeric;
        return;
    end if;
    if requested_count = 0 then
        return query select false, 'No seats were selected.', 0, 0::numeric;
        return;
    end if;

    select count(distinct requested.seat_id)::integer into distinct_count
    from unnest(p_seat_ids) as requested(seat_id);
    if distinct_count <> requested_count then
        return query select false, 'Duplicate seats were supplied.', 0, 0::numeric;
        return;
    end if;

    -- Lock every existing requested seat in stable order before checking status.
    -- This serializes concurrent seat selection and avoids the invalid aggregate
    -- SELECT ... FOR UPDATE used by migration 001.
    perform ss.id
    from show_seats ss
    where ss.show_id = p_show_id and ss.id = any(p_seat_ids)
    order by ss.id
    for update;

    select count(*)::integer, coalesce(sum(ss.price), 0)
      into available_count, calculated_total
    from show_seats ss
    where ss.show_id = p_show_id and ss.id = any(p_seat_ids)
      and (
        ss.status = 'available'
        or (ss.status = 'locked' and ss.locked_until <= now())
        or (ss.status = 'locked' and ss.locked_by = p_user_id)
      );

    if available_count <> requested_count then
        return query select false, 'One or more selected seats are unavailable.', 0, 0::numeric;
        return;
    end if;

    update show_seats
       set status = 'locked',
           locked_until = now() + make_interval(mins => p_lock_minutes),
           locked_by = p_user_id
     where show_id = p_show_id and id = any(p_seat_ids);

    return query select true, 'Seats locked successfully.', requested_count, calculated_total;
end;
$$;
