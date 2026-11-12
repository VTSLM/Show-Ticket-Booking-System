# Shared Database

The unified TicketFlow backend connects to the team's single Supabase/PostgreSQL database.
The canonical, ordered SQL migrations are maintained in `../database/migrations/`:

1. `001_initial_schema.sql`
2. `002_payment_gateway.sql`
3. `003_reviews_module.sql`
4. `004_review_deletions.sql`

Do not create a second database for the Reviews & Ratings feature. Apply the new migrations
to the existing shared database after the existing schema migrations.
