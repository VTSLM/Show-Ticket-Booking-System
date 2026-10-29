# Feature 05 integration notes

## This package now includes the integration adapters

- `backend/main.py`: existing isolated standalone demo with SQLite and the no-build preview UI.
- `backend/shared_main.py`: shared PostgreSQL/Firebase-authenticated payment API. It queries the team's real `bookings` / `booking_seats` / `show_seats`, writes to `payment_orders` / `payments` / `receipts`, and rejects live Razorpay keys.
- `backend/app.py`: selects the shared mode when `PAYMENT_STORAGE=postgres`; demo mode is explicit (`PAYMENT_STORAGE=demo`). If unset, the mode defaults to PostgreSQL when `DATABASE_URL` is present and otherwise to demo.
- `frontend/components/payment/PaymentCheckout.jsx` and `.css`: namespaced premium checkout component for the team's existing React/Next.js UI. It receives a booking UUID and Firebase ID-token getter from host code. No method selector is shown; Razorpay Checkout handles method selection.
- `sprint1/database/migrations/002_payment_gateway.sql`: feature-specific migration shipped at the shared migration path in this integration-ready archive.

## Dependencies/interfaces

**Feature 01:** React host passes `user.getIdToken()` via `getAccessToken`. Backend verifies the Firebase ID token with Firebase Admin, then maps the token UID to `users.firebase_uid` and derives the internal `users.id`. A raw `user_id` from browser input is never trusted.

**Features 02–03:** they remain the source of the selected show. Feature 05 reads title, venue, screen and showtime from the existing persisted booking and joins, rather than maintaining its own catalogue or demo title.

**Feature 04:** it must create the pending `bookings` and `booking_seats` records and hold the corresponding `show_seats` locks for the authenticated user. The payment API uses the saved `bookings.total_amount`; it does not accept amount/price from the frontend. At order creation, all selected seats must still be locked to the booking owner. On captured payment, the backend locks and validates those rows and atomically marks seats `booked` plus booking `confirmed`. If the locks expired/reassigned, payment is recorded as captured but the booking remains unconfirmed in `successful_needs_review`; this state blocks another charge and needs team reconciliation/refund handling.

**Feature 06:** only generate tickets/QRs when the shared booking status is confirmed—not merely from the client-side Razorpay callback.

## Migration

`sprint1/database/migrations/002_payment_gateway.sql` adds `payment_orders` and extends `payments` with provider identifiers/status metadata. It adds uniqueness for Razorpay payment/order IDs, prevents multiple unresolved orders per booking, and replaces the invalid aggregate/`FOR UPDATE` seat-lock function. Apply it after `001_initial_schema.sql`.

The existing shared `001_initial_schema.sql` has a seat-locking bug: `lock_show_seats()` tries `FOR UPDATE` with an aggregate query, which PostgreSQL does not allow. The new `002_payment_gateway.sql` migration replaces it with a corrected function that locks selected rows first and then computes count/amount inside the same transaction. Applying migration 002 is required for this correction; the original 001 remains unchanged.

## Verification / operational limitations

- Standalone demo SQLite is still available for UI preview and remains separate from shared mode.
- Shared mode requires a real `DATABASE_URL`, an applied feature migration and server-side Firebase Admin credentials. It cannot be end-to-end verified without those private team settings.
- Razorpay Test Mode only (`rzp_test_` guard). The earlier standalone payment test reported by the developer does not automatically verify this new PostgreSQL mode; retest once configured.
- Webhook signature verification/replay handling, alerts, rate limiting and a formal operational refund workflow should be added before live money is ever considered. This feature continues to reject live keys.
