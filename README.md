# TicketFlow — Show Ticket Booking System

> IT314 Software Engineering · DA-IICT · Batch 2024 · Sprint 1

A full-stack event ticketing platform built as a university software engineering project. Users can browse shows, select seats, pay via Razorpay, and download e-tickets with QR codes. Venue managers can create and schedule events. Admins approve managers and manage the platform.

---

## Tech Stack

| Layer        | Technology                                      |
|--------------|-------------------------------------------------|
| Frontend     | Next.js 14.2 (App Router, TypeScript, Tailwind) |
| Backend      | FastAPI (Python 3.9) + asyncpg                  |
| Database     | PostgreSQL via Supabase (Session Pooler)         |
| Auth         | Firebase Authentication (Email/Password)         |
| Payments     | Razorpay (Test Mode)                             |
| Email        | Gmail SMTP (App Password)                        |
| PDF / QR     | ReportLab + qrcode + Pillow                      |

---

## Repository Structure

```
Show-Ticket-Booking-System/
│
├── sprint1/                        # Individual feature branches work (pre-integration)
│   ├── database/
│   │   └── migrations/
│   │       ├── 001_initial_schema.sql      # Core schema (users, venues, shows, bookings…)
│   │       └── 002_payment_gateway.sql     # payment_orders table + payments columns
│   ├── features/
│   │   ├── 01-authentication/      # Firebase Auth — register, login, role guard
│   │   ├── 02-manager-show-listing/ # Venue manager dashboard — events, screens, shows
│   │   ├── 03-browse-nearby-shows/ # Public show browsing with filters
│   │   ├── 04-seat-allocation/     # Real-time seat map, locking, WebSocket broadcast
│   │   ├── 05-payment/             # Razorpay checkout, order creation, verification
│   │   └── 06-ticket-generation/   # QR code, PDF e-ticket, email delivery
│   └── shared/
│
├── sprint1_v2/                     # ✅ Integrated system (use this to run the app)
│   ├── backend/                    # Unified FastAPI backend (all 6 features merged)
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── firebase_admin_setup.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   ├── routers/
│   │   │   ├── auth.py             # /auth/register, /auth/verify-token, /admin/*
│   │   │   ├── manager.py          # /api/manager/venues, screens, events, shows
│   │   │   ├── browse.py           # /api/browse/shows, cities, event-types
│   │   │   ├── seats.py            # /api/seats/{show_id}/map, lock, release, ws
│   │   │   ├── bookings.py         # /api/bookings (create, get, list)
│   │   │   ├── payments.py         # /api/payments/orders, verify, receipts
│   │   │   └── tickets.py          # /api/tickets/confirm, pdf, verify
│   │   └── services/
│   │       ├── ticket_service.py   # PDF generation (ReportLab)
│   │       ├── qr_service.py       # QR code generation
│   │       └── email_service.py    # Gmail SMTP email with PDF attachment
│   │
│   ├── frontend/                   # Next.js 14 frontend (App Router)
│   │   └── app/
│   │       ├── auth/               # Login / Register pages
│   │       ├── browse/             # Show listing + filters
│   │       ├── shows/              # Show detail page
│   │       ├── bookings/           # Seat selection + booking confirmation
│   │       ├── payment/            # Razorpay checkout + verification
│   │       ├── manager/            # Manager dashboard
│   │       └── admin/              # Admin dashboard
│   │
│   ├── database/                   # SQL migrations (copy of sprint1/database)
│   ├── INTEGRATION_NOTES.md        # 📖 Full setup guide for developers
│   ├── docker-compose.yml
│   └── start-dev.sh                # One-command dev startup
│
└── Documentation/                  # Requirements PDF, stakeholder elicitation
```

---

## Features

| # | Feature | Status | Owner |
|---|---------|--------|-------|
| F01 | **User Authentication** — Firebase Email/Password, role-based access (customer / manager / admin) | ✅ Done | Janak / Arpit |
| F02 | **Manager Show Listing** — Create venues, screens, events, schedule shows, auto-generate seats | ✅ Done | Vatsal Mori |
| F03 | **Browse Nearby Shows** — Filter by city, event type, language, date, search | ✅ Done | Dwij Patel |
| F04 | **Seat Allocation** — Real-time seat map, 10-min seat locking, WebSocket broadcast | ✅ Done | Vatsal Mori / Khushi |
| F05 | **Payment Gateway** — Razorpay order creation, HMAC signature verification, booking confirmation | ✅ Done | Darshan |
| F06 | **Ticket Generation** — QR code, PDF e-ticket download, Gmail email delivery | ✅ Done | Hari Sharma |

---

## Sprint 1 — What Was Built

Sprint 1 covers the full user journey end to end:

```
Browse Shows → Select Seats (locked for 10 min) → Create Booking
    → Razorpay Payment → Verify Signature → Confirm Booking
        → Generate Ticket (QR + PDF) → Email Delivery
```

Each of the 6 features was developed independently on a separate branch. After individual development, all 6 were integrated into a single unified backend and frontend in `sprint1_v2/`.

### Key integration work done
- Merged 6 separate FastAPI backends into one `main.py` with shared DB pool, Firebase auth, and dependency injection
- Fixed `booking_number` NOT NULL constraint (was missing from INSERT)
- Fixed `verify_payment` endpoint — wrong column names (`locked_by_user_id` → `locked_by`, `method` → `payment_method`), and `receipts` schema mismatch (`booking_id` doesn't exist — only `payment_id`)
- Fixed `get_receipt` JOIN path through `payments` table
- Fixed expired seat lock timezone comparison bug
- Fixed ReportLab PDF crash caused by emoji in Paragraph
- Resolved `.gitignore` merge conflict; added `.env` and Firebase key exclusions
- Created `INTEGRATION_NOTES.md` as a full developer handoff document

---

## Branch Guide

| Branch | Purpose |
|--------|---------|
| `main` | Base project — documentation and initial schema only |
| `integration/feature-merging` | ✅ **Active** — integrated sprint1_v2 system lives here |
| `feature/05-payment-gateway` | F05 standalone (Darshan) |
| `ticket-generation-hari` | F06 standalone (Hari) |
| `managers-can-list` | F02 standalone (Vatsal) |
| `browse-nearby-shows` | F03 standalone (Dwij) |
| `seat-allocation-vatsal` | F04 standalone (Vatsal) |
| `seat-allocation-khushi` | F04 standalone (Khushi) |
| `login` | F01 standalone |
| `DwijPatel` | F03 standalone (Dwij) |

---

## Database Setup

Run these SQL files in order in your **Supabase SQL Editor**:

```sql
-- Step 1: Core schema
sprint1/database/migrations/001_initial_schema.sql

-- Step 2: Payment gateway tables
sprint1/database/migrations/002_payment_gateway.sql

-- Step 3: Tickets table (run manually — not in any migration file)
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
```

> ⚠️ Do **not** run `sprint1/features/06-ticket-generation/backend/migrations/002_tickets_f6.sql` — it creates a `tickets` table with a different schema that conflicts with the backend.

---

## Running Locally (sprint1_v2)

### 1. Backend

```bash
cd sprint1_v2/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create .env (copy from below, fill in your values)
uvicorn main:app --reload --port 8000
```

**`sprint1_v2/backend/.env`**
```env
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
FIREBASE_SERVICE_ACCOUNT_PATH=./ticketflow-firebase.json
RAZORPAY_KEY_ID=rzp_test_Tv37OCcTyHjb8d
RAZORPAY_KEY_SECRET=i2sBZ8kAjP0xeZbcs43hWvS7
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
FRONTEND_URL=http://localhost:3000
```

### 2. Frontend

```bash
cd sprint1_v2/frontend
npm install
npm run dev
```

**`sprint1_v2/frontend/.env.local`**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyDlfHxoDYcbAIjXj1RRbKSBNxoYBqcZyXE
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=ticketflow-71a4d.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=ticketflow-71a4d
```

> See `sprint1_v2/INTEGRATION_NOTES.md` for the complete setup guide including test data SQL, admin role assignment, and Razorpay test credentials.

---

## Testing Payments (Razorpay Test Mode)

| Method | Details |
|--------|---------|
| **Netbanking** | Select any bank → any username/password → Submit ✅ (most reliable) |
| **Card** | `5267 3181 8797 5449` · Expiry: `12/28` · CVV: `123` · OTP: `1234` |
| ❌ Avoid | `4111 1111 1111 1111` — fails with "International card not supported" |

---

## Known Issues / Open TODOs

See the [GitHub Issues](../../issues) tab for all open items. Key ones:

1. Ticket PDF download needs end-to-end testing after a real payment
2. Gmail email delivery requires each developer to set up their own App Password
3. UPI option not showing in Razorpay modal — use Netbanking instead
4. Manager dashboard (`/manager`) not yet tested in integrated environment
5. Admin dashboard (`/admin`) not yet tested in integrated environment
6. No background job to clean up expired seat locks

---

## Team

| Member | DA-IICT ID | Role |
|--------|-----------|------|
| Vatsal Mori | 202401471 | F02 Manager Listing, F04 Seat Allocation, Integration |
| Hari Sharma | 202401195 | F06 Ticket Generation, Integration & Bug Fixes |
| Darshan | — | F05 Payment Gateway |
| Janak / Arpit | — | F01 Authentication |
| Dwij Patel | — | F03 Browse Shows |
| Khushi | — | F04 Seat Allocation |

---

## Documents

- [`sprint1_v2/INTEGRATION_NOTES.md`](sprint1_v2/INTEGRATION_NOTES.md) — Developer handoff: full setup, all changes, test data SQL, known issues
- [`Documentation/Requirements_v1.pdf`](Documentation/Requirements_v1.pdf) — Project requirements
- [`Documentation/Stakeholders-Elicitation.pdf`](Documentation/Stakeholders-Elicitation.pdf) — Stakeholder elicitation report
- [`sprint1/COLLABORATION.md`](sprint1/COLLABORATION.md) — Git branching workflow guide
