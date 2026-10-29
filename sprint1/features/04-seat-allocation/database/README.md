# Database setup — Feature 04 Seat Allocation

Both source branches use the same Supabase/PostgreSQL project but currently model seats differently.

## Migration order

1. Run `002_customer_seat_selection.sql` first. It creates the customer/show booking model (`seats`, `show_seats`, `bookings`, and related functions).
2. Run `001_manager_layout.sql` to create the manager layout editor's `layouts` and `layout_seats` tables.

## Important integration limitation

The manager UI currently saves a reusable layout to `layouts` / `layout_seats`. The customer seat-selection API reads show-specific seat state from `seats` / `show_seats`. These tables are not synchronized by the supplied code.

Therefore, creating or editing a manager layout does **not yet automatically change the seat map customers see**. Before treating this as a fully integrated production feature, add and test an explicit publish/sync operation that maps a ready layout to physical `seats` for its screen and initializes `show_seats` for each relevant show. That operation must preserve booked/locked show-seat state and map manager categories to the customer schema's allowed `seat_type` values (`standard`, `premium`, `accessible`); arbitrary manager category strings cannot be inserted directly into that constrained column.

Do not drop either schema or replace the existing `seats` table without a reviewed migration.
