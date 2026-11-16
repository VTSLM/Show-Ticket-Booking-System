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
| 0007 | `005_venue_application_fields.sql` |
| 0008 | `004_cancellation_refund.sql` |
| 0009 | `003_reviews_module.sql` |
| 0010 | `004_review_deletions.sql` |
| 0011 | `006_multi_venue_layouts.sql` |
| 0012 | `004_critics_and_reviews.sql` |
| 0013 | `005_review_scheduling_and_replies.sql` |
| 0014 | `007_verified_events_venues.sql` |
| 0015 | `006_fuzzy_search_pg_trgm.sql` |
| 0016 | `007_review_reports.sql` |
| 0017 | `008_dynamic_seat_pricing.sql` |
| 0018 | `008_show_details_layout_and_terms.sql` |
| 0019 | `001_ai_review_summaries.sql` |
| 0020 | `009_wishlist.sql` |

Databases that already have these applied (the shared Supabase project) do not need to re-run anything. Only the file names changed.
