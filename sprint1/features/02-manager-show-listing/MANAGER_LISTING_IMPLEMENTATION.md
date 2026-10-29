# Manager Event & Show Listing Module — Implementation Report

## 1. Executive Summary
This document records the complete architecture, implementation decisions, database integration, API contracts, environment setup, and test verification for the **Manager Event and Show Listing Module** (Sprint 1, Feature 02: *Managers Can List*).

- **Module Directory**: `sprint1/features/02-manager-show-listing/`
- **Frontend Stack**: Next.js 14, React 18, Tailwind CSS (Visual design directly modelled after the reference [Dribbble Cinema App](https://dribbble.com/shots/18941569-Cinema-App) with electric blue glowing device frames, gradient poster overlays, perforated ticket tear dividers with side cutouts, clean metadata grids, and white QR stub handoff cards)
- **Backend Stack**: FastAPI (Python 3.13), async PostgreSQL connection pool (`asyncpg`), Pydantic v2
- **Database**: PostgreSQL hosted on Supabase (mapped strictly against the existing schema)
- **Authentication & Authorization**: Firebase Auth (mapped to `users.firebase_uid`), role authorization enforced via `user_roles` and `roles` table
- **Teammate Boundary**: Handoff to Feature 04 (*Seat Selection & Show Pricing*) via `/pricing?show_id={id}&event_id={id}&screen_id={id}&seat_count={count}` and `GET /api/manager/shows/{id}/handoff`

---

## 2. Supabase Database Schema Mapping
All database operations adapt strictly to the existing Supabase PostgreSQL tables without modifying, recreating, dropping, or migrating any tables:

| Table | Columns Used by Module | Constraints & Data Types | Purpose in Manager Workflow |
| :--- | :--- | :--- | :--- |
| **`events`** | `id` (uuid, PK)<br>`title` (varchar)<br>`description` (text)<br>`event_type` (enum)<br>`duration_minutes` (int)<br>`language` (varchar)<br>`genre` (varchar)<br>`poster_url` (text)<br>`status` (enum)<br>`created_at`, `updated_at` | `event_type`: `'movie'`, `'concert'`, `'theatre'`, `'other'`<br>`status`: `'draft'`, `'published'`, `'inactive'`<br>`duration_minutes > 0` | Stores movies created by managers. Fixed to Cinema (`movie`). Poster images are stored as Cloudinary URLs in `poster_url`. |
| **`venues`** | `id` (uuid, PK)<br>`name` (varchar)<br>`address` (text)<br>`city` (varchar)<br>`state` (varchar)<br>`pincode` (varchar) | Non-null `name`, `city` | Venues/cinemas available for show scheduling. |
| **`screens`** | `id` (uuid, PK)<br>`venue_id` (FK `venues.id`)<br>`name` (varchar)<br>`capacity` (int) | `capacity > 0` | Auditorium screens within venues. Provides baseline physical capacity. |
| **`seats`** | `id` (uuid, PK)<br>`screen_id` (FK `screens.id`)<br>`row_label` (varchar)<br>`seat_number` (int)<br>`seat_type` (enum) | `seat_type`: `'standard'`, `'premium'`, `'accessible'` | Physical seat layout for a screen. Queried to calculate exact seat counts. |
| **`layouts`** | `id` (uuid, PK)<br>`screen_id` (uuid)<br>`approved_capacity` (int)<br>`status` (text) | `status`: `'draft'`, `'ready'`, `'archived'` | Visual screen layout configuration. Inspected as fallback for capacity. |
| **`shows`** | `id` (uuid, PK)<br>`event_id` (FK `events.id`)<br>`screen_id` (FK `screens.id`)<br>`start_time` (timestamptz)<br>`end_time` (timestamptz)<br>`status` (enum)<br>`created_at`, `updated_at` | `status`: `'scheduled'`, `'cancelled'`, `'completed'`<br>`end_time > start_time` | Scheduled showtimes for events. Conflict detection prevents overlapping shows on the same screen. |
| **`show_seats`** | `id` (uuid, PK)<br>`show_id` (FK `shows.id`)<br>`seat_id` (FK `seats.id`)<br>`price` (numeric)<br>`status` (enum) | `show_seat_status`: `'available'`, `'locked'`, `'booked'`, `'reserved'`<br>`price >= 0` | Populated and priced exclusively by the teammate's pricing module. Empty upon initial show creation. |
| **`users`** | `id` (uuid, PK)<br>`firebase_uid` (varchar, unique)<br>`name` (varchar)<br>`email` (varchar, unique)<br>`status` (enum) | `user_status`: `'active'`, `'inactive'`, `'blocked'` | Maps Firebase authenticated user identity to database user. |
| **`roles`** | `id` (uuid, PK)<br>`code` (varchar, unique)<br>`name` (varchar) | Codes: `'customer'`, `'manager'`, `'admin'` | Role definitions. |
| **`user_roles`** | `user_id` (FK `users.id`)<br>`role_id` (FK `roles.id`) | Composite PK `(user_id, role_id)` | Associates users with roles. Verified by backend authorization. |

---

## 3. Files Created and Modified

### A. Feature & Shared Configuration
- [`sprint1/features/02-manager-show-listing/MANAGER_LISTING_IMPLEMENTATION.md`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/MANAGER_LISTING_IMPLEMENTATION.md) (Moved): Progress and integration guide.
- [`sprint1/.env.example`](file:///d:/Sem%205/Se_project/sprint1/.env.example) (Modified): Documented `DATABASE_URL` and `DEV_BYPASS_AUTH`.
- [`sprint1/features/02-manager-show-listing/README.md`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/README.md) (Modified): Architecture and module guide.
- [`sprint1/features/02-manager-show-listing/docs/TODO.md`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/docs/TODO.md) (Modified): Completed design and architectural decisions.

### B. FastAPI Backend (`sprint1/features/02-manager-show-listing/backend/`)
- [`backend/requirements.txt`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/requirements.txt): Backend dependencies (`fastapi`, `uvicorn`, `asyncpg`, `pytest`, etc.).
- [`backend/.env.example`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/.env.example): Backend environment template.
- [`backend/app/config.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/config.py): Application settings and environment loader.
- [`backend/app/database.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/database.py): Supabase PostgreSQL connection pool with SSL support, health check, and parameterized queries.
- [`backend/app/auth.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/auth.py): Firebase ID token verification and database role-based authorization for managers.
- [`backend/app/models.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/models.py): Pydantic request/response models with enum validations.
- [`backend/app/services/event_service.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/services/event_service.py): Database queries and business logic for events.
- [`backend/app/services/seat_service.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/services/seat_service.py): Authoritative seat count calculation logic.
- [`backend/app/services/show_service.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/services/show_service.py): Show scheduling, interval conflict prevention, and handoff generator.
- [`backend/app/routers/events.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/routers/events.py): API routes for events.
- [`backend/app/routers/venues.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/routers/venues.py): API routes for venues and screens.
- [`backend/app/routers/screens.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/routers/screens.py): API route for screen seat count verification.
- [`backend/app/routers/shows.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/routers/shows.py): API routes for shows and pricing handoff.
- [`backend/app/main.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/app/main.py): FastAPI application entry point with CORS and health checks.

### C. Backend Automated Test Suite (`backend/tests/`)
- [`backend/tests/conftest.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/conftest.py): Fixtures with `TestClient` and mock authenticated managers.
- [`backend/tests/test_api_events.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/test_api_events.py): Tests for valid creation, missing fields, enum validation, and DB error handling.
- [`backend/tests/test_api_shows.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/test_api_shows.py): Tests for show creation, invalid event/screen references, and timing validation.
- [`backend/tests/test_conflicts_and_validation.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/test_conflicts_and_validation.py): Tests for overlapping show conflict prevention.
- [`backend/tests/test_seat_count.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/test_seat_count.py): Tests for authoritative seat count derivation and fallbacks.
- [`backend/tests/test_auth_and_roles.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/test_auth_and_roles.py): Tests for 401 unauthenticated and 403 non-manager rejection.
- [`backend/tests/test_handoff.py`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/backend/tests/test_handoff.py): Tests for teammate pricing handoff contract.

### D. Next.js Frontend (`sprint1/features/02-manager-show-listing/frontend/`)
- [`frontend/package.json`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/package.json): Next.js 14, React 18, Tailwind CSS dependencies.
- [`frontend/tailwind.config.js`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/tailwind.config.js): Custom cinema color tokens and glassmorphism styling.
- [`frontend/postcss.config.js`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/postcss.config.js): PostCSS Tailwind setup.
- [`frontend/next.config.js`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/next.config.js): Next.js config with remote image domains for Cloudinary.
- [`frontend/tsconfig.json`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/tsconfig.json): TypeScript configuration.
- [`frontend/lib/types.ts`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/lib/types.ts): Data contracts for Events, Shows, Venues, Screens, and Handoffs.
- [`frontend/lib/api.ts`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/lib/api.ts): API client executing HTTP requests to the FastAPI backend.
- [`frontend/components/Navbar.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/components/Navbar.tsx): Cinema-themed header with real-time database connection status badge.
- [`frontend/components/StatsBar.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/components/StatsBar.tsx): Metrics overview for events, shows, screens, and pending pricing counts.
- [`frontend/components/EventList.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/components/EventList.tsx): Movie and event catalogue cards with poster preview and direct schedule actions.
- [`frontend/components/ShowList.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/components/ShowList.tsx): Scheduled shows table with session times, capacity, and teammate handoff links.
- [`frontend/components/CreateEventModal.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/components/CreateEventModal.tsx): Event creation form with real-time validation and Cloudinary poster preview.
- [`frontend/components/CreateShowModal.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/components/CreateShowModal.tsx): Show scheduling modal with cascading venue/screen dropdowns, live seat count preview, and automatic duration/buffer calculations.
- [`frontend/app/globals.css`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/app/globals.css): Dark theme tokens, glassmorphism, and custom scrollbars.
- [`frontend/app/layout.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/app/layout.tsx): Root application layout.
- [`frontend/app/page.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/app/page.tsx): Main manager dashboard view with tab switching and alerts.
- [`frontend/app/pricing/page.tsx`](file:///d:/Sem%205/Se_project/sprint1/features/02-manager-show-listing/frontend/app/pricing/page.tsx): Teammate pricing module integration boundary interface.

---

## 4. Key Architectural & Business Decisions

### A. Determining the Physical Seat Count (Step D)
The teammate's seat-category and pricing module requires the exact number of seats for a scheduled screen. The backend (`app/services/seat_service.py`) calculates this authoritatively using the database:
1. **Primary Source — Physical Seats**: Queries `SELECT count(*) FROM seats WHERE screen_id = :screen_id`. If rows exist in the `seats` table, this count is used (`source = "seats_table"`).
2. **Secondary Source — Screen Layout**: If no seat rows exist, queries `approved_capacity` from `layouts` where `screen_id = :screen_id` (`source = "layouts_table"`).
3. **Tertiary Fallback — Screen Baseline Capacity**: Fallback to `screens.capacity` (`source = "screens_capacity"`), which is a non-null positive integer in PostgreSQL.

*Note*: No fake seat rows are created, and the database schema is unmodified. Both `seat_count` and its `source` are returned to the frontend and handoff contract.

### B. Show Publication & Public Booking Safeguards (Step F)
- Creating a show in the database sets `shows.status = 'scheduled'`.
- **CRITICAL SAFEGUARD**: Creating a show **DOES NOT** make it publicly bookable.
- Under the database model, public ticket booking requires `show_seats` rows with a valid `price >= 0` and status `'available'`.
- Upon show creation, no `show_seats` records exist. The show is returned with `pricing_ready: false`.
- Only after the teammate's Feature 04 module configures seat tier prices (e.g. Standard, Premium) and generates `show_seats` records does the show open for customer bookings.

### C. Teammate Handoff Contract (Step E)
When a show is created:
1. The frontend immediately navigates to:
   ```
   /pricing?show_id={show_id}&event_id={event_id}&screen_id={screen_id}&seat_count={seat_count}
   ```
2. The pricing module queries the backend handoff endpoint:
   ```http
   GET /api/manager/shows/{show_id}/handoff
   ```
3. Backend returns the authoritative handoff JSON:
   ```json
   {
     "show_id": "sh111111-1111-1111-1111-111111111111",
     "event_id": "e1111111-1111-1111-1111-111111111111",
     "event_title": "Inception 2",
     "venue_id": "v1111111-1111-1111-1111-111111111111",
     "venue_name": "Demo Cinema",
     "screen_id": "s1111111-1111-1111-1111-111111111111",
     "screen_name": "Screen 1",
     "start_time": "2026-10-15T18:00:00Z",
     "end_time": "2026-10-15T20:15:00Z",
     "status": "scheduled",
     "seat_count": 100,
     "pricing_ready": false,
     "pricing_route": "/pricing?show_id=sh111111-1111-1111-1111-111111111111&event_id=e1111111-1111-1111-1111-111111111111&screen_id=s1111111-1111-1111-1111-111111111111&seat_count=100",
     "integration_notes": "Handoff to Feature 04: Seat categories and pricing must be configured before show is publicly bookable."
   }
   ```

### D. Scheduling Conflict Prevention
Before saving a show to Supabase, the backend verifies that the screen is not already occupied:
```sql
SELECT id FROM shows
WHERE screen_id = $1
  AND status = 'scheduled'
  AND start_time < $3
  AND end_time > $2;
```
If an overlap exists, the API returns `409 Conflict` with a clear explanation, preventing double bookings on the same screen.

---

## 5. API Endpoints Specification

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/manager/health` | Health & database connection check | None |
| `GET` | `/api/manager/events` | List all events/movies | Manager Role |
| `POST` | `/api/manager/events` | Create a new event | Manager Role |
| `GET` | `/api/manager/events/{id}` | Get event details | Manager Role |
| `GET` | `/api/manager/venues` | List venues and their screens | Manager Role |
| `GET` | `/api/manager/venues/{id}/screens` | List screens for a venue | Manager Role |
| `GET` | `/api/manager/screens/{id}/seat-count` | Get physical seat count breakdown | Manager Role |
| `GET` | `/api/manager/shows` | List all scheduled shows | Manager Role |
| `POST` | `/api/manager/shows` | Schedule a show & validate conflicts | Manager Role |
| `GET` | `/api/manager/shows/{id}` | Get show details | Manager Role |
| `GET` | `/api/manager/shows/{id}/handoff` | Teammate pricing handoff payload | Manager Role |

---

## 6. How to Run Locally

### 1. Configure Environment Variables
In `sprint1/features/02-manager-show-listing/backend/.env`:
```ini
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
DEV_BYPASS_AUTH=true
CLOUDINARY_CLOUD_NAME=demo
```

In `sprint1/features/02-manager-show-listing/frontend/.env.local`:
```ini
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### 2. Start the FastAPI Backend
```powershell
cd "d:\Sem 5\Se_project\sprint1\features\02-manager-show-listing\backend"
python -m uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger docs will be available at: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/manager/health`

### 3. Run Backend Automated Tests
```powershell
cd "d:\Sem 5\Se_project\sprint1\features\02-manager-show-listing\backend"
python -m pytest tests/
```
Result: **15 passed** in 0.20s.

### 4. Start the Next.js Frontend
```powershell
cd "d:\Sem 5\Se_project\sprint1\features\02-manager-show-listing\frontend"
& "C:\Program Files\nodejs\npm.cmd" run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 7. How to Test Real Supabase Database Inserts

1. Set your team's live Supabase database URL in `backend/.env`:
   ```ini
   DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```
2. Verify connectivity:
   Open `http://localhost:8000/api/manager/health`. You will receive:
   ```json
   {
     "status": "online",
     "database": {
       "status": "healthy",
       "message": "Connected to Supabase PostgreSQL database.",
       "database_connected": true
     }
   }
   ```
3. Create an Event:
   - On the frontend dashboard, click **+ New Event**.
   - Enter title `"Avatar 3"`, type `"movie"`, duration `180`, genre `"Sci-Fi"`.
   - Click **Save Event**.
   - Check the Supabase dashboard -> Table Editor -> `events`: the new row with UUID, title, and timestamps will appear.
4. Schedule a Show:
   - Click **+ Schedule Show**.
   - Select `"Avatar 3"`, select the venue and screen (the screen's capacity will appear).
   - Choose a date and start time.
   - Click **Schedule Show & Open Pricing**.
   - Check the Supabase dashboard -> Table Editor -> `shows`: the show row with `event_id`, `screen_id`, and `scheduled` status is saved.
   - Notice the browser seamlessly navigates to the `/pricing` handoff page ready for your teammate!
