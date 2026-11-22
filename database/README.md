# Database

TicketFlow uses PostgreSQL (Supabase today, Azure Database for PostgreSQL planned). All schema changes live here as plain SQL.

```text
database/
├── migrations/   # Ordered, forward-only schema changes. Apply in filename order.
├── rollbacks/    # Optional undo scripts, named after the migration they reverse.
├── seeds/        # Test and demo data. Never run against production.
└── schema.sql    # Generated snapshot of the full schema after the last migration.
```

## Rules

- **Never edit a migration that has been merged.** Fix mistakes with a new migration.
- Name new files `NNNN_short_description.sql` with the next free four-digit number. If two open PRs take the same number, the second one to merge renumbers.
- Make migrations safe to run twice where possible (`IF NOT EXISTS`, `DO $$ ... EXCEPTION WHEN duplicate_object ...`).
- Every new table that Supabase exposes should have row level security enabled, as the existing migrations do.
- Regenerate `schema.sql` in the same PR (see below).
- CI applies every migration to an empty Postgres 16 database. A PR that breaks the chain cannot merge.

## Apply locally

```bash
docker compose --profile localdb up -d db      # empty Postgres with all migrations applied on first start
psql postgresql://ticketflow:ticketflow@localhost:5432/ticketflow -f database/seeds/001_test_data.sql
```

Or against any database:

```bash
for f in database/migrations/*.sql; do psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"; done
```

## Demo catalogue (seed 005)

`seeds/005_demo_catalogue.py` fills Browse for demos: 10 cities, multiplexes with cinema seat maps, an arena
(stage, standing zones, grandstand), an auditorium and a comedy club per city, 10 movies, fictional live events
and showtimes for the next 7 days. Posters are original title cards served from the public
Supabase Storage bucket `demo-posters`: generate them with `python scripts/generate_demo_posters.py`, upload the
files to the top level of that bucket, then run the seed (it builds the links from `SUPABASE_URL`, or from
`DEMO_POSTER_BASE_URL` if set).

It is the one seed meant for the shared demo deployment. It costs about 13 MB of database space per day of
showtimes, so keep `--days` small on the free Supabase plan, and run it again every few days to keep showtimes ahead.

```bash
cd backend
venv/bin/python ../database/seeds/005_demo_catalogue.py --dry-run   # see what it would add
venv/bin/python ../database/seeds/005_demo_catalogue.py             # add / extend (safe to repeat)
venv/bin/python ../database/seeds/005_demo_catalogue.py --remove    # take it down
```

## Regenerate schema.sql

```bash
docker compose --profile localdb down -v && docker compose --profile localdb up -d db
docker compose exec db pg_dump -U ticketflow --schema-only --no-owner --no-privileges ticketflow > database/schema.sql
```

## History

Before v0.3.0 the migrations were spread over sprint folders with clashing numbers. They were renumbered by the date each file was first committed:

| New | Old name |
|-----|----------|
| 0001 | `sprint1/database/migrations/001_initial_schema.sql` |
| 0002 | `sprint1/database/migrations/002_payment_gateway.sql` |
| 0003 | `unified_schema.sql` (step 2.5 onwards) |
| 0004 | `003_customer_care.sql` |
| 0005 | `004_organizer_verification.sql` |
| 0006 | `004_admin_verification_person_b.sql` |
| 0007 | *new:* `venue_verification_cases` and `venue_verification_audit`, which existed only in Supabase |
| 0008 | `005_venue_application_fields.sql` |
| 0009 | `004_cancellation_refund.sql` |
| 0010 | `003_reviews_module.sql` |
| 0011 | `004_review_deletions.sql` |
| 0012 | `006_multi_venue_layouts.sql` |
| 0013 | `004_critics_and_reviews.sql` |
| 0014 | `005_review_scheduling_and_replies.sql` |
| 0015 | `007_verified_events_venues.sql` |
| 0016 | `006_fuzzy_search_pg_trgm.sql` |
| 0017 | `007_review_reports.sql` |
| 0018 | `008_dynamic_seat_pricing.sql` |
| 0019 | `008_show_details_layout_and_terms.sql` |
| 0020 | `001_ai_review_summaries.sql` |
| 0021 | `009_wishlist.sql` |
| 0022 | *new:* aligns fresh databases with Supabase (`shows.base_price`, venue status column, row level security) |

Databases that already have these applied (the shared Supabase project) do not need to re-run anything. Only the file names changed. `0007` and `0022` were reconstructed from a schema-only dump of Supabase and change nothing when run there.

## Known differences from the shared Supabase database

A schema dump of Supabase (2026-11-16) compared with a fresh database built from these migrations:

- **Only in Supabase, not used by the code:** tables `layouts` and `layout_seats`, functions `create_pending_booking`, `confirm_booking_payment`, `cancel_pending_booking`, `release_booking_seats`, and the Firebase wrapper foreign table `public."user"` (Supabase-specific). Left out on purpose.
- **Only in the migrations:** `0006` (`verification_cases`, `audit_log`, `listing_reviews`, `listing_reports`, `venue_compliance`, `checklist_templates`), the trigram search indexes from `0016` and several indexes and constraints on `payments`, `payment_orders` and `tickets` were never applied to Supabase. Code that uses them (organizer verification admin, fuzzy search) works on a fresh database but not fully on Supabase until they are applied there.
- Column types differ in places (`text` in Supabase where the migrations say `varchar`). The app does not depend on the difference.
