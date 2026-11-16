# TicketFlow — Integration Notes & Developer Handoff

> **Branch:** `integration/feature-merging`  
> **Last updated:** 2026-11-03  
> **Author:** Hiri (Hari Sharma, 202401195) — IT314 Software Engineering, DA-IICT

---

## What Was Integrated

This document covers all the fixes and wiring done to get the end-to-end booking flow working: Browse Shows → Select Seats → Proceed to Payment → Razorpay → Ticket Download.

---

## Stack

| Layer     | Technology                            |
|-----------|---------------------------------------|
| Frontend  | Next.js 14.2.3 (App Router, TypeScript) |
| Backend   | FastAPI + asyncpg (Python 3.9)        |
| Database  | Supabase (PostgreSQL) — Session Pooler |
| Auth      | Firebase Auth (Email/Password)        |
| Payments  | Razorpay (test mode)                  |
| Email     | Gmail SMTP (app password)             |

---

## Project Structure

```
ticketflow/
├── backend/              ← FastAPI app (run with uvicorn)
│   ├── main.py
│   ├── config.py
│   ├── database.py       ← asyncpg pool with SSL for Supabase
│   ├── dependencies.py   ← Firebase token verification
│   ├── routers/
│   │   ├── auth.py
│   │   ├── browse.py
│   │   ├── seats.py
│   │   ├── bookings.py
│   │   ├── payments.py
│   │   └── tickets.py
│   └── services/
│       ├── ticket_service.py
│       ├── qr_service.py
│       └── email_service.py
├── frontend/             ← Next.js app (run with npm run dev)
│   ├── app/
│   └── ...
├── sprint1/database/migrations/
│   ├── 001_initial_schema.sql   ← Run this FIRST in Supabase
│   └── 002_payment_gateway.sql  ← Run this SECOND
└── sprint1/features/06-ticket-generation/backend/migrations/
    └── 002_tickets_f6.sql       ← NOT used — see tickets table below
```

---

## Setup Instructions (for a new developer)

### 1. Prerequisites

- Python 3.9+ (NOT 3.10+ for type hint compatibility)
- Node.js 18+
- A Supabase project (free tier works)
- A Firebase project with Email/Password auth enabled
- A Razorpay account (test mode keys)

---

### 2. Database Setup (Supabase)

Go to your Supabase project → **SQL Editor** and run the following in order:

**Step 1 — Core schema:**
```
sprint1/database/migrations/001_initial_schema.sql
```

**Step 2 — Payment gateway tables:**
```
sprint1/database/migrations/002_payment_gateway.sql
```

**Step 3 — Tickets table** (run this manually, the F6 migration has wrong columns):
```sql
CREATE TABLE IF NOT EXISTS tickets (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id   uuid NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
    user_id      uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    show_id      uuid NOT NULL REFERENCES shows(id) ON DELETE RESTRICT,
    qr_code_data text,
    status       varchar(20) NOT NULL DEFAULT 'valid',
    is_used      boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tickets_booking_id ON tickets(booking_id);
CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
```

**Step 4 — Seed roles** (if roles table is empty):
```sql
INSERT INTO roles (name, code, description) VALUES
  ('Customer', 'customer', 'Regular ticket buyer'),
  ('Manager',  'manager',  'Venue/event manager'),
  ('Admin',    'admin',    'System administrator')
ON CONFLICT (code) DO NOTHING;
```

> **Important:** The `roles` table uses a `code` column (lowercase: `customer`, `manager`, `admin`) — not `name`. The backend always checks `roles.code`.

---

### 3. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` (copy from `.env.example` and fill in your values):

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
FIREBASE_SERVICE_ACCOUNT_PATH=/absolute/path/to/your-firebase.json
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxx
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
FRONTEND_URL=http://localhost:3000
SECRET_KEY=change-this-in-production
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_...
SUPABASE_ANON_KEY=sb_publishable_...
```

> **Supabase DATABASE_URL note:** Use the **Session Pooler** URL from Supabase → Settings → Database → Connection string (URI mode). The host is `aws-0-<region>.pooler.supabase.com` on port **5432**. URL-encode any special characters in the password (e.g. `+` → `%2B`).

**Run the backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

Backend runs at: http://localhost:8000  
API docs: http://localhost:8000/docs

---

### 4. Frontend Setup

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSy...          # Must be lowercase 'l' in 'Dlf' — double-check from Firebase Console
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<project-id>
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=<project-id>.firebasestorage.app
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=<number>
NEXT_PUBLIC_FIREBASE_APP_ID=1:<number>:web:<hex>
```

**Run the frontend:**
```bash
cd frontend
npm run dev
```

Frontend runs at: http://localhost:3000

---

### 5. Firebase Setup

In the [Firebase Console](https://console.firebase.google.com):
1. Go to **Authentication → Sign-in method**
2. Enable **Email/Password**
3. Download the **Service Account JSON** (Project Settings → Service Accounts → Generate new private key)
4. Place it at the path set in `FIREBASE_SERVICE_ACCOUNT_PATH` in your `.env`

---

### 6. Insert Test Data

Run these in Supabase SQL Editor to get a testable show:

```sql
-- Venue
INSERT INTO venues (id, name, address, city, state, country, total_screens)
VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'PVR Ahmedabad', 'SG Highway', 'Ahmedabad', 'Gujarat', 'India', 1)
ON CONFLICT DO NOTHING;

-- Screen
INSERT INTO screens (id, venue_id, name, total_capacity)
VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Screen 1', 30)
ON CONFLICT DO NOTHING;

-- Seats (rows A–C, 10 seats each)
INSERT INTO seats (screen_id, row_label, seat_number, seat_type)
SELECT 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
       chr(64 + ceil(n::float/10)::int),
       ((n-1) % 10) + 1,
       'standard'
FROM generate_series(1,30) n
ON CONFLICT DO NOTHING;

-- Event
INSERT INTO events (id, title, type, status, language, genre)
VALUES ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'Pushpa 2', 'movie', 'published', 'Hindi', 'Action')
ON CONFLICT DO NOTHING;

-- Show (tomorrow at 6 PM)
INSERT INTO shows (id, event_id, screen_id, start_time, status)
VALUES ('dddddddd-dddd-dddd-dddd-dddddddddddd',
        'cccccccc-cccc-cccc-cccc-cccccccccccc',
        'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        now() + interval '1 day' + interval '18 hours',
        'scheduled')
ON CONFLICT DO NOTHING;

-- Show seats at ₹200 each
INSERT INTO show_seats (show_id, seat_id, price, status)
SELECT 'dddddddd-dddd-dddd-dddd-dddddddddddd', id, 200.00, 'available'
FROM seats
WHERE screen_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
ON CONFLICT DO NOTHING;
```

---

### 7. Assign Admin Role to Your User

After registering via the app, find your user's UUID in Supabase (users table), then:

```sql
INSERT INTO user_roles (user_id, role_id)
SELECT '<your-user-uuid>', id FROM roles WHERE code = 'admin'
ON CONFLICT DO NOTHING;
```

---

## Changes Made During Integration

### `backend/database.py`
- Added explicit SSL context (`CERT_NONE`) for Supabase Session Pooler connection
- Added `from __future__ import annotations` for Python 3.9 compatibility (no `X | None` syntax)

### `backend/routers/browse.py`
- Fixed `s.base_price` → `MIN(ss.price) as base_price` in both show listing queries  
  (the `shows` table has no `base_price` column; price lives on `show_seats`)

### `backend/routers/seats.py`
- Fixed `locked_by_user_id` → `locked_by` (actual column name in `show_seats`)
- Removed the block that released **all** of a user's locks when locking any new seat (was breaking multi-seat selection)

### `backend/routers/bookings.py`
- Added `booking_number` generation (`TF-YYYYMMDD-XXXXXX`) to the INSERT  
  (`bookings.booking_number` is NOT NULL UNIQUE — was causing 500 errors)
- Added `import uuid as uuid_module` and `from datetime import datetime`

### `backend/routers/payments.py` — `verify_payment` endpoint
- Fixed `locked_by_user_id` → `locked_by` in the `show_seats` UPDATE
- Fixed `payments` INSERT: `method` → `payment_method` (it's an enum column)
- Fixed `receipts` INSERT: removed non-existent `booking_id` column; now correctly inserts `payment_id` (FK to `payments.id`)
- Restructured the whole function inside a single `conn.transaction()` block

### `frontend/.env.local`
- Fixed Firebase API key: had uppercase `L` (`AIzaSyDLf...`) — must be lowercase `l` (`AIzaSyDlf...`)

### `backend/dependencies.py` / auth
- Backend role check uses `roles.code` (lowercase: `customer`, `manager`, `admin`) — not `roles.name`
- `users.status` column (enum: `active`/`inactive`/`blocked`) — not `is_active`

---

## Testing the Payment Flow (Razorpay Test Mode)

Use these test credentials in the Razorpay modal:

**Netbanking (easiest):** Select any bank → any credentials → Submit  

**UPI:** `success@razorpay`

**Card:**
- Number: `5267 3181 8797 5449`
- Expiry: `12/28`  
- CVV: `123`
- OTP: `1234`

> Note: `4111 1111 1111 1111` fails with "international card not supported" — use the Mastercard above or Netbanking.

---

## Known Remaining Issues / TODO for Teammates

- [ ] **Ticket PDF download** — needs testing after a successful payment
- [ ] **Email sending** — configured via Gmail SMTP; may need Gmail App Password set up per developer
- [ ] **Seat lock expiry** — locks expire after 5 minutes; expired seats become available again automatically
- [ ] **Manager dashboard** (`/manager`) — event/show creation UI needs testing
- [ ] **Admin dashboard** (`/admin`) — user management needs testing
- [ ] **`sprint1/features/06-ticket-generation/backend/migrations/002_tickets_f6.sql`** — do NOT run this; it creates a differently-structured `tickets` table that conflicts with the backend router. Use the `CREATE TABLE tickets` SQL in Step 3 of setup above instead.

---

## Quick Command Reference

```bash
# Backend
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm run dev

# Check backend is alive
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

---

## Architecture: Request Flow

```
Browser (localhost:3000)
    │
    ├─ Firebase Auth → ID Token
    │
    └─ API calls to localhost:8000
           │
           ├─ dependencies.py verifies Firebase token
           │       └─ looks up user in Supabase users table
           │
           ├─ routers/browse.py    → GET /api/browse/shows
           ├─ routers/seats.py     → POST /api/seats/{show_seat_id}/lock
           ├─ routers/bookings.py  → POST /api/bookings   (creates pending booking)
           ├─ routers/payments.py  → POST /api/payments/orders  (creates Razorpay order)
           │                       → POST /api/payments/orders/{id}/verify (after payment)
           └─ routers/tickets.py   → POST /api/tickets/bookings/{id}/confirm
                                   → GET  /api/tickets/bookings/{id}/pdf
```

