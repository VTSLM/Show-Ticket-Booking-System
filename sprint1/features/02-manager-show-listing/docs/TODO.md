# Manager Show Listing — Architecture & Integration Decisions

- **User flow**:
  1. Manager signs in via Firebase Auth (or uses dev header `X-Dev-Firebase-Uid: DEV_FIREBASE_UID_MANAGER` in local development).
  2. Opens `/` (Manager Dashboard), which displays event catalogue and scheduled shows.
  3. **Event Creation**: Manager inputs title, event type, duration, language, genre, Cloudinary poster URL, status. Persisted in Supabase `events`.
  4. **Show Scheduling**: Manager selects event, venue, screen, and showtime. Screen seat count is queried live. Time overlap conflicts are blocked. Persisted in Supabase `shows` with status `'scheduled'`.
  5. **Teammate Handoff**: Show creation triggers immediate redirect to `/pricing?show_id={show_id}&event_id={event_id}&screen_id={screen_id}&seat_count={seat_count}`.

- **API contract**:
  - `GET /api/manager/events`: Lists all events
  - `POST /api/manager/events`: Inserts event row in `events` table
  - `GET /api/manager/venues`: Lists venues with associated screens
  - `GET /api/manager/screens/{screen_id}/seat-count`: Returns authoritative seat count and capacity
  - `GET /api/manager/shows`: Lists scheduled shows
  - `POST /api/manager/shows`: Validates and inserts show row in `shows` table
  - `GET /api/manager/shows/{show_id}/handoff`: Supplies exact payload for Feature 04 pricing module

- **Database dependency (`supabase_schema_reference.txt`)**:
  - Tables used: `users`, `roles`, `user_roles`, `events`, `venues`, `screens`, `seats`, `shows`, `show_seats`, `layouts`.
  - Zero schema modifications made.

- **Dependencies on other features**:
  - Feature 01 (Authentication): Firebase Auth user ID mapped to `users.firebase_uid`.
  - Feature 04 (Seat Selection & Pricing): Show is created with `pricing_ready: false`. Feature 04 must assign seat tier prices before the show is publicly bookable.

- **Test cases**:
  - All 15 unit and integration tests passing in `backend/tests/`.
  - Automated tests cover event creation, missing fields, invalid enums, show scheduling, conflict detection, seat count calculation, manager role authorization, and teammate handoff contract.
