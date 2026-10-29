create extension if not exists pgcrypto;

create table if not exists public.layouts (
    id uuid primary key default gen_random_uuid(),
    screen_id uuid,
    screen_name text not null,
    rows integer not null check (rows > 0 and rows <= 100),
    columns integer not null check (columns > 0 and columns <= 100),
    approved_capacity integer not null default 0 check (approved_capacity >= 0),
    status text not null default 'draft' check (status in ('draft','ready','archived')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.layout_seats (
    id uuid primary key default gen_random_uuid(),
    layout_id uuid not null references public.layouts(id) on delete cascade,
    row_index integer not null check (row_index >= 0),
    col_index integer not null check (col_index >= 0),
    label text not null,
    category text,
    price numeric(10,2),
    status text not null default 'available' check (status in ('available','blocked')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(layout_id,row_index,col_index),
    unique(layout_id,label),
    check (price is null or price >= 0)
);

create index if not exists idx_layouts_screen_id on public.layouts(screen_id);
create index if not exists idx_layout_seats_layout_id on public.layout_seats(layout_id);

create or replace function public.manager_layout_set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists trg_layouts_updated_at on public.layouts;
create trigger trg_layouts_updated_at before update on public.layouts
for each row execute function public.manager_layout_set_updated_at();

drop trigger if exists trg_layout_seats_updated_at on public.layout_seats;
create trigger trg_layout_seats_updated_at before update on public.layout_seats
for each row execute function public.manager_layout_set_updated_at();
