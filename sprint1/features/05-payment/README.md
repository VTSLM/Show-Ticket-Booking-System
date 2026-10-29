# Feature 05 — Cinepass Payment Gateway

Integration-ready Razorpay **Test Mode** checkout for the Show Ticket Booking System. This package now includes two paths:

- **Shared integration path:** FastAPI + Firebase ID-token verification + the team's shared Supabase/PostgreSQL schema. This path is selected with `PAYMENT_STORAGE=postgres` and uses the React component at `frontend/components/payment/PaymentCheckout.jsx` in the team's existing React/Next.js frontend.
- **Standalone preview path:** the earlier no-build HTML/CSS/JavaScript checkout and SQLite sample records, selected with `PAYMENT_STORAGE=demo`. This is only for isolated UI testing; it is not the team's persisted booking flow.

The shared path loads the persisted booking and total from PostgreSQL; it never accepts an amount or internal user ID from the browser. It verifies Firebase ID tokens, checks booking ownership and live seat locks, creates an order with Razorpay, verifies checkout signatures, fetches authoritative provider status, and confirms a booking only after Razorpay reports `captured` **and** the booking's seat locks still belong to that user. If money was captured but seat locks no longer validate, the order enters `successful_needs_review`, remains blocked from a second payment, and displays a clear review-needed state.

Payment-method selection happens inside Razorpay Checkout. The Key Secret remains server-only. Both paths reject non-`rzp_test_` keys.

## Shared integration setup

1. This integration-ready archive places the feature migration directly at `sprint1/database/migrations/002_payment_gateway.sql`. Apply it after `001_initial_schema.sql` in the shared Supabase SQL Editor. **Do not re-run the seed file against production data.**
2. In the standalone archive, configure the private `.env` beside this README. Once merged into the team repo, place shared settings in `sprint1/.env` (do not create a feature-level `.env` that could override shared values). Set `PAYMENT_STORAGE=postgres`, the server-only `DATABASE_URL`, `PAYMENT_PROVIDER=razorpay`, Razorpay Test Mode credentials, and Firebase Admin credentials. Prefer `GOOGLE_APPLICATION_CREDENTIALS` or managed workload identity. Otherwise set `FIREBASE_SERVICE_ACCOUNT_PATH` to a private service-account JSON file stored outside Git.
3. Install backend dependencies using `./run_local.sh`; the script runs `backend.app:app`, which selects the mode from environment configuration.
4. Import `frontend/components/payment/PaymentCheckout.jsx` into the team's React/Next.js payment page. See [`frontend/components/payment/README.md`](frontend/components/payment/README.md) and [`USAGE_EXAMPLE.jsx`](frontend/components/payment/USAGE_EXAMPLE.jsx). Feature 04 should navigate with the persisted pending booking UUID; Feature 01's Firebase user should supply `user.getIdToken()` through `getAccessToken`.
5. Set `NEXT_PUBLIC_BACKEND_URL` to the API origin if frontend and backend use different origins, and set backend `FRONTEND_ORIGINS` to the frontend origin. Never place a database URL, service-role key, Firebase Admin private key, or Razorpay Key Secret in a `NEXT_PUBLIC_*` variable.

## Local standalone preview

The no-build preview keeps using the original SQLite demo booking. To explicitly use it, set `PAYMENT_STORAGE=demo` in `.env`, configure Razorpay Test Mode credentials, then run `./run_local.sh`. Visit <http://127.0.0.1:8000>. The React component is the intended shared-app frontend; the standalone HTML page is not the main app's React frontend.

## API routes (shared mode)

All booking/order/receipt routes require `Authorization: Bearer <Firebase ID token>` and are scoped to the internal user mapped by `users.firebase_uid`.

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Non-secret readiness and storage mode |
| `GET` | `/api/payments/booking/{booking_id}` | Load only the authenticated user's booking |
| `POST` | `/api/payments/orders` | Create a Razorpay order using persisted booking total and seat locks |
| `GET` | `/api/payments/orders/{order_id}` | Read the user's order state |
| `POST` | `/api/payments/orders/{order_id}/verify` | Verify checkout signature and reconcile provider status |
| `POST` | `/api/payments/orders/{order_id}/recheck` | Reconcile the same order; never creates a new order |
| `GET` | `/api/payments/receipts/{receipt_number}` | Read the authenticated user's receipt |

## Database contract

The existing team schema's `bookings.total_amount` is the only persisted payable amount, so the shared frontend displays the booking total rather than inventing convenience-fee/tax line items. `payment_orders` records provider order IDs and unresolved status. `payments` stores payment IDs, provider method, capture status, signature verification time and provider timestamp. `receipts` remains linked to the corresponding `payments` row.

## Important integration boundaries

- Replace the example auth-provider import in `USAGE_EXAMPLE.jsx` with the actual Feature 01 auth hook.
- Feature 04 must create the pending booking and lock each selected `show_seats` row for the authenticated `users.id`. The new `002_payment_gateway.sql` migration also replaces `lock_show_seats()` with a corrected function: it locks seat rows first and then computes the count/total in the transaction because PostgreSQL rejects `FOR UPDATE` on an aggregate query.
- If a payment is captured after the seat lock expires or ownership changes, the backend does not double-book seats or let the user pay again. It records the captured payment and returns `successful_needs_review`; the team must reconcile/refund that order operationally.
- This implementation uses synchronous provider status checks. Add signed webhook reconciliation, replay/idempotency handling, rate limits and operational alerts before any live-payment release. Live Razorpay keys remain rejected here intentionally.

## Run and checks

Run the dependency-light shared helper tests with `python -m unittest discover -s tests -v`. These are unit tests only; they do not replace a live Supabase/Razorpay Test Mode integration run.

Fedora instructions: [`FEDORA_RUN.md`](FEDORA_RUN.md). API contract: [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). Integration steps: [`docs/INTEGRATION_NOTES.md`](docs/INTEGRATION_NOTES.md).
