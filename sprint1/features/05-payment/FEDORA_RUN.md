# Fedora run instructions — Feature 05

The backend uses Python/FastAPI. The shared frontend component is React/Next.js and should be imported into the team's existing frontend. Node/npm are not needed to run the backend itself. The bundled standalone preview is plain HTML/CSS/JavaScript.

## 1. Open the feature folder

After extracting the ZIP at the root of the team repository:

```bash
cd sprint1/features/05-payment
```

## 2. Configure settings privately

For team integration, put the shared values in `sprint1/.env` (not in a tracked file). The app checks the feature-local `.env` first if one exists, then the shared Sprint 1 `.env`. For PostgreSQL mode, set:

```dotenv
PAYMENT_STORAGE=postgres
PAYMENT_PROVIDER=razorpay
DATABASE_URL=postgresql://...your-private-supabase-connection...?...sslmode=require
RAZORPAY_KEY_ID=rzp_test_your_actual_test_key_id
RAZORPAY_KEY_SECRET=your_actual_test_key_secret
FIREBASE_SERVICE_ACCOUNT_PATH=/private/path/to/firebase-admin-service-account.json
FRONTEND_ORIGINS=http://localhost:3000
```

Use the team's agreed Supabase/PostgreSQL URI and Firebase Admin credentials. If the host uses `GOOGLE_APPLICATION_CREDENTIALS` or workload identity, the explicit service-account path can remain blank. Keep the DB URI, Firebase private key and Razorpay Key Secret out of frontend code and Git. Replace every placeholder before starting shared mode.

The feature `.env.example` is a template only. When this feature has been merged into the team repo, prefer the shared `sprint1/.env` rather than creating a second feature-level `.env` with duplicate credentials.

For a local preview only, set `PAYMENT_STORAGE=demo` and configure Razorpay Test Mode credentials. This uses the bundled SQLite demo booking; it does not test the shared PostgreSQL integration. Do not expose that preview as the team's integrated payment page.

## 3. Apply the feature migration

The archive contains `sprint1/database/migrations/002_payment_gateway.sql` at the intended repository path. Apply it after `001_initial_schema.sql` using the team's migration process / Supabase SQL Editor before running shared mode. It adds payment-order persistence and fixes the `lock_show_seats()` aggregate/`FOR UPDATE` problem. Never run development seed data against production data.

## 4. Start FastAPI

```bash
chmod +x run_local.sh
./run_local.sh
```

- Shared mode root: `http://127.0.0.1:8000/` (service information)
- API readiness: `http://127.0.0.1:8000/api/health`
- API docs: `http://127.0.0.1:8000/docs`
- Demo preview UI (when `PAYMENT_STORAGE=demo`): `http://127.0.0.1:8000/`

## 5. Connect the React frontend

Import `frontend/components/payment/PaymentCheckout.jsx` and its CSS into the team's existing React/Next.js frontend. Pass the Firebase user's ID-token getter to `getAccessToken`, the pending booking UUID from Feature 04 to `bookingId`, and the FastAPI origin to `apiBaseUrl`. See `frontend/components/payment/USAGE_EXAMPLE.jsx`; replace its illustrative auth import with the team's actual Feature 01 provider.

Set backend `FRONTEND_ORIGINS` to the exact frontend origin if frontend/backend are on different ports/domains. Set frontend `NEXT_PUBLIC_BACKEND_URL` to the API origin if required. Only the backend may read the database URL, Firebase Admin credentials and Razorpay Key Secret.

## 6. Payment recovery

If Checkout closes or returns a failure event, the component checks the same Razorpay Order ID before showing a retry option. While provider status is uncertain, it keeps the existing order and offers verification only. If Razorpay captured a payment but the seat locks expired or were reassigned, the result becomes `successful_needs_review`; do not pay again.

## 7. Validation limits

The source package passed syntax checks, helper tests, demo-mode smoke checks, and route/auth guard smoke checks. I could not run the migration against the team's actual Supabase database or exercise shared mode with their Firebase Admin credentials. Re-test the shared end-to-end browser flow after applying the migration and configuring those private settings. The earlier successful Razorpay Test Mode transaction was on the standalone path; it does not automatically validate the new shared-database path.
