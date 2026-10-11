# Manager Show Listing Module (Sprint 1)

This module implements Feature 02: **Managers Can List Shows & Create Events**.

## Architecture
- **Frontend (`frontend/`)**: Next.js 14 / React application with Tailwind CSS (Cinema dark aesthetic).
- **Backend (`backend/`)**: FastAPI server connecting to Supabase PostgreSQL via `asyncpg`.
- **Database**: Supabase PostgreSQL adhering strictly to `supabase_schema_reference.txt`.
- **Handoff**: Directly integrates with Feature 04 (Seat Selection & Pricing) via `/pricing?show_id=...`.

## Completed Capabilities
- [x] Manager operations dashboard with dark cinema aesthetics.
- [x] Event creation supporting title, description, event_type, duration, language, genre, Cloudinary poster URL, and status.
- [x] Show scheduling with venue and screen selection, start/end time, and conflict prevention.
- [x] Authoritative physical seat count calculation (`seats` -> `layouts` -> `screens.capacity`).
- [x] Public booking readiness enforcement (shows remain unpriced and unbookable until Feature 04 configures prices).
- [x] Teammate pricing handoff contract and interface (`/pricing`).
- [x] Full automated test suite (15/15 tests passing).

## Running the Module

### Backend
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
