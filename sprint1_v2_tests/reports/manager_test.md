# Manager Listing Feature — Testing README

## 1. Overview

This document describes the testing strategy, test scenarios, automation, test data, and execution procedure for the **Manager Listing** ("Manager Can List") feature of the Show Ticket Booking System (`sprint1_v2`).

The Manager Listing feature allows authorized Managers and Admins to:

- View and create cinema venues
- Configure screens with capacity and row × column seat grids
- Create and update events (movies, concerts, theatre, other)
- Schedule shows with automated end-time calculation and conflict prevention
- Populate `show_seats` atomically from physical screen seats (or fallback capacity)
- Delete unbooked shows safely while blocking deletion of shows with bookings
- Enforce role-based access control (`manager` / `admin` only)

The testing covers the backend API, frontend UI, edge cases, and frontend-to-backend integration.

---

## 2. Testing Scope

### In Scope

1. Venue creation and mandatory field validation
2. Screen creation with seat grid (`rows × cols`) and capacity-only mode
3. Event creation and partial updates (`PATCH /api/manager/events/{event_id}`)
4. Show creation and automatic `show_seats` inventory population
5. Validation of `end_time > start_time` and positive `base_price`
6. Server-side scheduling overlap detection (`409 Conflict` per C21)
7. Show deletion and booking reference protection (`409 Conflict`)
8. Role-based access control (`customer` rejected with `403`, unauthenticated rejected)
9. Manager Dashboard tabs (`Shows`, `Events`, `Venues`), screen loading, and route guards
10. Frontend-to-backend integration and Browse Shows visibility checks

### Out of Scope

- Payment gateway order creation and signature verification
- Ticket QR/PDF/email generation
- Customer seat locking during checkout

These are covered under their respective feature testing suites.

---

# 3. Testing Approach

The Manager Listing feature uses three levels of automated testing:

### 3.1 Backend/API Testing

Tests the FastAPI Manager router (`backend/routers/manager.py`) directly using `TestClient` against a schema-aware PostgreSQL test double (`SchemaAwareFakeConn` enforcing `001_initial_schema.sql` constraints).

```text
Pytest
   ↓
FastAPI TestClient
   ↓
Manager Router (/api/manager/*)
   ↓
Schema-Aware Fake AsyncPG / Database
```

### 3.2 Frontend/UI Testing

Tests the Manager Dashboard (`/manager`) independently using **Playwright** with Google Chrome (`channel: "chrome"`).

Firebase Auth REST calls (`mockAuth.ts`) and `/api/manager/*` endpoints are intercepted with `page.route` so frontend flows and error states run deterministically offline.

```text
Playwright (Chrome)
   ↓
Next.js Manager Page (/manager)
   ↓
Mocked Firebase Auth + Mocked Manager API
```

### 3.3 Integration Testing

Tests the real application flow without mocking Manager APIs (`manager-integration.spec.ts`), using real Manager credentials (`TEST_MANAGER_EMAIL`, `TEST_MANAGER_PASSWORD`).

```text
Playwright (Chrome)
   ↓
Next.js Frontend (/manager)
   ↓
FastAPI Backend
   ↓
Supabase/PostgreSQL
```

---

# 4. Tools Used

| Tool | Purpose |
|---|---|
| Pytest | Backend/API testing |
| Playwright | Frontend and integration testing (Google Chrome) |
| FastAPI | Backend API |
| Next.js | Frontend |
| Supabase/PostgreSQL | Database |
| TypeScript | Playwright test & helper implementation |

---

# 5. Test File Structure

```text
sprint1_v2/
│
├── pytest.ini
├── backend/
│   └── tests/
│       ├── conftest.py
│       └── test_manager.py
│
└── frontend/
    ├── playwright.config.ts
    └── tests/
        ├── helpers/
        │   └── mockAuth.ts
        └── manager/
            ├── manager.spec.ts
            ├── manager-edge.spec.ts
            ├── manager-integration.spec.ts
            └── manager_test.md
```

---

# 6. Backend/API Tests

## File

```text
backend/tests/test_manager.py
```

### Backend Test Scenarios

| Test ID | Description | Result |
|---|---|---|
| `test_man_001` | Create venue with valid payload (`200 OK`) | Passed |
| `test_man_002` | Reject venue missing mandatory fields (`422`) | Passed |
| `test_man_003` | Create screen with `2×10` grid generates 20 `seats` | Passed |
| `test_man_004` | Create capacity-only screen without `rows`/`cols` | Passed |
| `test_man_005` | Create event saves default status `'draft'` | Passed |
| `test_man_006` | `PATCH /events/{id}` updates whitelisted fields and strips disallowed keys | Passed |
| `test_man_007` | Create show populates fallback `seats` and `show_seats` atomically | Passed |
| `test_man_008` | Reject show where `end_time <= start_time` (`400 Bad Request`) | Passed |
| `test_man_009` | Reject overlapping scheduled show on same screen (`409 Conflict`) | Passed |
| `test_man_010` | Enforce RBAC (`customer` returns `403`, unauthenticated rejected) | Passed |
| `test_man_011` | Admin deletes unbooked show (`200`) and blocked on booked show (`409`) | Passed |
| `test_man_012` | Unpublished `'draft'` event show blocked on `GET /api/browse/shows/{id}` | XFAIL (`DEF-MAN-02`) |

### Backend Result

```text
11 passed, 1 xfailed
```

---

# 7. Frontend/UI & Edge-Case Tests

## 7.1 `manager.spec.ts` (Basic UI)

| Test ID | Test Scenario | Result |
|---|---|---|
| `MGR-UI-01` | Manager dashboard loads `Shows`, `Events`, `Venues` tabs and show list | Passed |
| `MGR-UI-02` | Selecting a Venue enables Screen dropdown and loads venue screens | Passed |
| `MGR-UI-03` | Manager creates a new Venue and sees toast + updated list | Passed |
| `MGR-UI-04` | Manager creates a new Screen (`2×10` -> `20 seats`) | Passed |
| `MGR-UI-05` | Manager creates a new Event in `Events` tab | Passed |
| `MGR-UI-06` | Manager schedules a Show with auto-calculated `End Time` | Passed |
| `MGR-UI-07` | Manager deletes an existing Show after confirmation dialog | Passed |

**Result: 7 passed**

---

## 7.2 `manager-edge.spec.ts` (Edge Cases)

| Test ID | Test Scenario | Expected & Observed Result | Result |
|---|---|---|---|
| `MGR-EDGE-01` | Enter `End Time <= Start Time` | Inline validation warning shown; `POST /api/manager/shows` blocked client-side | Passed |
| `MGR-EDGE-02` | Backend returns `409 Conflict` for overlapping show | Conflict toast displayed clearly to manager | Passed |
| `MGR-EDGE-03` | Select Venue with 0 screens | Screen dropdown shows `"No screens in this venue"` | Passed |
| `MGR-EDGE-04` | Delete show that already has bookings (`409`) | Error toast displayed; show remains in list | Passed |
| `MGR-EDGE-05` | Submit Screen creation with `Rows = 0` | `"Rows and columns must be greater than 0"` toast shown | Passed |
| `MGR-EDGE-06` | Customer role opens `/manager` directly | Redirected back to `/` | Passed |

**Result: 6 passed**

---

# 8. Integration Tests

## File

```text
frontend/tests/manager/manager-integration.spec.ts
```

These tests do **not mock Manager APIs** and require a running backend and active Manager credentials.

| Test ID | Description | Result |
|---|---|---|
| `MGR-INT-01` | Manager dashboard loads real shows, events, and venues from backend | Skipped *(credentials not set)* |
| `MGR-INT-02` | Creating an event persists via real `POST /api/manager/events` | Skipped *(credentials not set)* |

---

# 9. Environment Configuration

Required environment variables only for `manager-integration.spec.ts`:

```powershell
$env:TEST_MANAGER_EMAIL="manager@example.com"
$env:TEST_MANAGER_PASSWORD="your-manager-password"
```

Mocked UI/edge tests (`manager.spec.ts`, `manager-edge.spec.ts`) run with zero external credentials.

---

# 10. Test Execution Commands

## 10.1 Backend Tests

From `sprint1_v2/`:

```bash
python -m pytest backend/tests/test_manager.py -v
```

## 10.2 Frontend UI & Edge Tests (Playwright Chrome)

From `sprint1_v2/frontend/`:

```bash
npx playwright test tests/manager/manager.spec.ts tests/manager/manager-edge.spec.ts
```

## 10.3 Integration Tests

Start backend (`uvicorn main:app --reload --port 8000`) and frontend (`npm run dev`), set `TEST_MANAGER_EMAIL` / `TEST_MANAGER_PASSWORD`, then run:

```bash
npx playwright test tests/manager/manager-integration.spec.ts --headed
```

---

# 11. Complete Manager Listing Test Summary

| Testing Layer | Total | Passed | XFailed / Expected Fail | Failed | Skipped |
|---|---:|---:|---:|---:|---:|
| Backend/API (`pytest`) | 12 | 11 | 1 | 0 | 0 |
| Frontend/UI (`manager.spec.ts`) | 7 | 7 | 0 | 0 | 0 |
| Frontend Edge (`manager-edge.spec.ts`) | 6 | 6 | 0 | 0 | 0 |
| Integration (`manager-integration.spec.ts`) | 2 | 0 | 0 | 0 | 2 |
| **Total** | **27** | **24** | **1** | **0** | **2** |

---

# 12. Application Defects Identified

### `DEF-MAN-01` — Events created via `/manager` stay `'draft'` and do not appear in Browse Shows
- **Severity:** High
- **Files:** `sprint1_v2/backend/routers/manager.py`, `sprint1_v2/frontend/app/manager/page.tsx`, `sprint1_v2/frontend/lib/api.ts`
- **Observation:** `EventCreate` defaults `status` to `"draft"`, and `/manager` has no status selector or **Publish** button (`managerApi` lacks `updateEvent`). Meanwhile `GET /api/browse/shows` filters `e.status = 'published'`, hiding all shows for UI-created events.

### `DEF-MAN-02` — Draft-event show details remain reachable via direct URL/API (`C06 NFR-03`)
- **Severity:** Medium
- **Covered By:** `test_man_012` (`XFAIL`)
- **File:** `sprint1_v2/backend/routers/browse.py` (`get_show_details`)
- **Observation:** `GET /api/browse/shows/{show_id}` filters `WHERE s.id=$1` without checking `e.status = 'published'` and `s.status = 'scheduled'`, returning `200 OK` instead of `404`.

### `DEF-MAN-03` — Managers cannot edit or delete venues and events
- **Severity:** Medium
- **Files:** `sprint1_v2/backend/routers/manager.py`, `sprint1_v2/frontend/app/manager/page.tsx`, `sprint1_v2/frontend/lib/api.ts`
- **Observation:** `PATCH/DELETE /api/manager/venues/{id}` and `DELETE /api/manager/events/{id}` are absent from the API and Dashboard UI, and venues/events lack manager ownership scoping (`C03 NFR-SM-06`).

---

# 13. Testing Conclusion

All **24 executable frontend UI, edge, and core backend checks** passed in Google Chrome and Pytest, verifying the show-creation fixes (`end_time > start_time`, conflict checks, fallback seats, RBAC). Open defects (`DEF-MAN-01`, `DEF-MAN-02`, `DEF-MAN-03`) are isolated and tracked above.

