# Common Database

This is the version-controlled Supabase/PostgreSQL database for the project.

## Files
- `migrations/001_initial_schema.sql` — enums, tables, constraints, indexes,
  timestamp triggers, and Seat Selection database functions.
- `seeds/001_test_data.sql` — small development dataset.

## Run
1. Create one Supabase project for the whole team.
2. Open Supabase SQL Editor.
3. Run the migration.
4. Run the seed script.
5. Verify the tables in Table Editor.
6. Test the Seat Selection RPC functions.

## Notes
The ER diagram names enum types but does not specify their allowed values.
The migration therefore uses proposed starter values; confirm them with the
team before treating the schema as final.

The diagram has `show_seats.locked_until` but does not show who owns a lock.
`locked_by` is added because temporary user-specific locking requires lock
ownership.

Firebase remains the authentication provider. `users.firebase_uid` maps an
application user to Firebase Auth. Passwords are not stored here.

Never commit Supabase service-role keys, Firebase private keys, Razorpay
secrets, or database passwords.
