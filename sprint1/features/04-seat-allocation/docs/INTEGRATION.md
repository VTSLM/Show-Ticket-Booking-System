# Feature 04 — Customer Seat Selection + Manager Seat Layout

## Combined scope

- Customer: show seat map, seat selection, holds, release, booking/payment simulation for local development, and seat-map polling.
- Manager: generate a seat grid, define aisle columns, set categories/prices, block/unblock seats, validate approved capacity, save layouts, and export a fixture.
- Shared application: one FastAPI backend and one Next.js frontend.

## Routes

### Customer
- `GET /api/shows/{show_id}/seat-map`
- `POST /api/shows/{show_id}/holds`
- `DELETE /api/holds/{booking_id}`
- Optional local-only simulator: `POST /api/dev/simulate-payment/{booking_id}` (only when explicitly enabled in local environment)

### Manager
- `GET /api/screens`
- `GET /api/layouts`
- `POST /api/layouts`
- `GET /api/layouts/{layout_id}`
- `PUT /api/layouts/{layout_id}`
- `POST /api/layouts/{layout_id}/bulk-update`
- `GET /api/layouts/{layout_id}/fixture`

## Frontend routes

- `/` — workflow landing page
- `/shows/{showId}/seats` — customer seat selection
- `/manager/layouts` — manager layout and pricing

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Configure DATABASE_URL for customer seat selection.
# Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY for manager layout APIs.
uvicorn app.main:app --reload --port 8000
```

The Supabase service-role key must stay backend-only. Do not place it in any `NEXT_PUBLIC_*` variable or commit `.env`.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`.

## Critical data-model integration note

The code from the two branches did not originally share one seat table. Customer selection reads `seats` and `show_seats`; manager layout editing writes `layouts` and `layout_seats`. Both routers are now mounted in the same backend, but the supplied code does not yet publish/synchronize a manager layout into customer show-seat records. See `database/README.md`. Do not claim end-to-end shared seat state until that publish flow and authorization are implemented and tested.

## Security and verification checklist

- Configure Firebase auth and protect manager endpoints so only manager/admin users can modify layouts. The original manager branch had `AUTH_REQUIRED=false` as a development setting; the combined router does not treat that as sufficient production authorization.
- Keep all credentials out of Git. Only `.env.example` files are included in this merged package.
- Run backend tests and frontend build in your project environment.
- Verify manager APIs with the same Supabase project used by the customer schema.
- Add integration tests for publishing layouts to shows, ensuring booked/locked seats are never overwritten.
