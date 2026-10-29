# Group leader merge checklist — Feature 05

This archive is laid out to merge at the **root of the team's repository**. It contains only Feature 05 source plus its required shared migration. It does not overwrite the team's current `sprint1/.env`, schema migration 001, or unrelated feature folders.

## File placement

- Files under `sprint1/features/05-payment/` merge into the existing Feature 05 folder.
- `sprint1/database/migrations/002_payment_gateway.sql` is a new shared migration. Apply it after `001_initial_schema.sql` using the agreed database migration process.

## Integration steps

1. Review `sprint1/features/05-payment/docs/INTEGRATION_NOTES.md` and `docs/API_CONTRACT.md`.
2. Add `SQLAlchemy`, `psycopg[binary]`, and `firebase-admin` to the backend environment that will run the shared adapter (the package's `backend/requirements.txt` lists them).
3. Add the payment environment variables from `.env.example` to the private `sprint1/.env`: `PAYMENT_STORAGE=postgres`, `DATABASE_URL`, `PAYMENT_PROVIDER=razorpay`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `FIREBASE_SERVICE_ACCOUNT_PATH` or workload credentials, and `FRONTEND_ORIGINS`. Never commit that file or the Firebase service-account JSON.
4. Import `frontend/components/payment/PaymentCheckout.jsx` and its CSS into the team's React/Next.js payment page. Replace the example auth import in `USAGE_EXAMPLE.jsx` with the actual Feature 01 auth hook. Pass the booking UUID from Feature 04 and the Firebase user's `getIdToken()` function.
5. Ensure Feature 04 creates `bookings` and `booking_seats` records and locks the associated `show_seats` for the owning internal `users.id`. The payment adapter will reject invalid/expired seat locks.
6. Ensure Feature 06 generates tickets only after the backend reports `booking_confirmation_status === 'confirmed'`.
7. Set `NEXT_PUBLIC_BACKEND_URL` if the browser frontend and FastAPI backend use different origins. Configure the API's `FRONTEND_ORIGINS` to match the frontend origin exactly.
8. Verify the Supabase migration, then test a Test Mode success, failed payment, Checkout dismissal, interrupted API/network recovery, duplicate callback, expired seat lock, and multi-user booking ownership. The existing user's successful standalone Test Mode test does not substitute for testing this new shared database adapter.

## Important contract

The browser sends a booking UUID, never an amount or internal user ID. The server validates the Firebase token, maps `firebase_uid` to `users.id`, fetches the total from `bookings.total_amount`, verifies Razorpay's signature and provider state, and transitions seats/booking in a transaction only when the payment is captured and the lock ownership is still valid. If funds are captured but seats cannot be confirmed, status `successful_needs_review` blocks another payment and requires operational reconciliation; it must not trigger a ticket.
