# Feature 05 validation notes

Validated in the source package on 27 October 2026:

- Python syntax compilation for `backend/app.py`, `backend/main.py`, and `backend/shared_main.py`.
- Four dependency-light unit tests for monetary conversion and provider reconciliation helpers.
- JSX syntax transpilation for `frontend/components/payment/PaymentCheckout.jsx` and `USAGE_EXAMPLE.jsx`.
- CSS parsing for the React checkout and the standalone preview stylesheet.
- Standalone HTML duplicate-ID and referenced asset checks.
- Demo-mode FastAPI smoke test: health, moved preview page, demo booking, mock order, mock successful payment, confirmation and receipt.
- Shared-mode API smoke test using an in-memory SQLite harness: health endpoint, Test Mode flag, and unauthenticated requests rejected with HTTP 401.
- Source ZIP layout is intended as a repository overlay with Feature 05 under `sprint1/features/05-payment/` and migration 002 under `sprint1/database/migrations/`.

Not claimed as verified here:

- Migration 002 was not executed against the team's actual Supabase/PostgreSQL project.
- Shared mode was not run with the team's real Firebase Admin credentials or DATABASE_URL; those are private and not included in this archive. The in-memory SQLite harness does not validate PostgreSQL SQL semantics or transaction behavior.
- The shared database + Razorpay Test Mode end-to-end flow must be tested after the migration is applied. The user's previously successful Razorpay test verified the earlier standalone path, not this new shared-database adapter.
- Real browser review inside the team's Next.js application, signed webhook handling, multi-user race testing, and reconciliation after interrupted real Test Mode transactions remain team integration checks.
