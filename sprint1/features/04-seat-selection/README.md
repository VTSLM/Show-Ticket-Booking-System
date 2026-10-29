# Person 1 — Manager Layout & Pricing Tool

Implements the requested workflow: data model -> grid generation -> bulk category/pricing -> individual override -> blocked seats -> capacity validation -> reusable layout -> fixture for Person 2.

## Why `layout_seats`?
Your shared database already contains core physical/show seat concepts. This feature adds `layouts` and `layout_seats` rather than silently changing the existing `seats` table. Once the team agrees on the final canonical seat schema, `layout_seats` can be mapped into it.

## Setup

### Supabase
Run `database/001_manager_layout.sql` in Supabase SQL Editor.

### Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```
Open http://localhost:3000/manager/layouts

## Test
1. Generate 5 x 8 seats with aisle columns `3,4`.
2. Select seats and apply `VIP` / `350`.
3. Select one seat and edit it individually.
4. Block a seat and confirm sellable count drops.
5. Set approved capacity below sellable count and confirm Save is rejected.
6. Price every sellable seat and Save Layout.
7. Reload the page and choose the saved layout under Existing layout to edit it.
8. Export Fixture and give the JSON to Person 2.

## Security
`SUPABASE_SERVICE_ROLE_KEY` is backend-only. Never put it in Next.js or commit it. `AUTH_REQUIRED=false` is only for local testing. Before production, connect the existing Firebase Auth middleware and restrict these endpoints to manager/admin users.
