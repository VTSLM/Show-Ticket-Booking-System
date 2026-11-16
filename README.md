# TicketFlow - Show Ticket Booking System

> **IT314 Software Engineering** · **DA-IICT** · **Batch 2024** · **Sprint 1 & Sprint 2 snapshots · Sprint 3 active**

TicketFlow is a modern, full-stack event ticketing platform developed as a university software engineering project. It provides an end-to-end event management and ticketing solution where users can discover upcoming events, select and lock seats in real time, make secure online payments via Razorpay, and receive instant e-tickets with scannable QR codes.

Venue managers can list and schedule events, while administrators manage access control and platform operations.

> **Status:** Sprint 1 and Sprint 2 are preserved as runnable snapshots. Continue development in `sprint3/`.

---

## Run a Sprint Locally

| Sprint | Application directory | Baseline |
|--------|-----------------------|----------|
| Sprint 1 | [`sprint1/integrated/`](sprint1/integrated/) | Original Sprint 1 integration, `c0a3d7a`. The original standalone modules and database files are also in `sprint1/`. |
| Sprint 2 | [`sprint2/`](sprint2/) | Completed integrated snapshot with fixes through `7ff0f85`. |
| Sprint 3 | [`sprint3/`](sprint3/) | Active application, starting from the same merged baseline as Sprint 2. |

From the selected application directory, run these commands in two terminals. Set up your local backend and frontend environment files for the team's test services before starting. Use the original setup notes for each snapshot. [Sprint 1 setup](sprint1/integrated/INTEGRATION_NOTES.md) · [Sprint 2 setup](sprint2/INTEGRATION_NOTES.md) · [Sprint 3 setup](sprint3/INTEGRATION_NOTES.md)

**Backend**

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

For the original Sprint 1 snapshot, run `python -m pip install 'setuptools==80.9.0'` before starting the backend. Its original Razorpay dependency uses `pkg_resources`.

**Frontend**

```sh
cd frontend
npm ci
npm run dev
```

Open [TicketFlow locally](http://localhost:3000). The frontend and backend commands use ports 3000 and 8000, so stop one sprint's servers before starting the next.

---

## 🛠️ Tech Stack

| **Layer** | **Technology** |
|-----------|----------------|
| **Frontend** | Next.js 14.2 (App Router, TypeScript, Tailwind CSS) |
| **Backend** | FastAPI (Python 3.9) + asyncpg |
| **Database** | PostgreSQL via Supabase (Session Pooler) |
| **Authentication** | Firebase Authentication (Email / Password) |
| **Payments** | Razorpay Payment Gateway (Test Mode) |
| **Email Delivery** | Gmail SMTP (App Password) |
| **PDF & QR Engine** | ReportLab + qrcode + Pillow |

---

## ✨ Features (Sprint 1)

| **#** | **Feature** | **Branch Name** | **Description** |
|-------|-------------|-----------------|-----------------|
| **F01** | **User Authentication** | `login` | Secure multi-role authentication (User, Manager, Admin) powered by Firebase. |
| **F02** | **Manager Show Listing** | `managers-can-list` | Dashboard for listing, scheduling, and configuring events and venues. |
| **F03** | **Browse & Search Shows** | `browse-nearby-shows` | Interactive event discovery with search and filtering capabilities. |
| **F04** | **Seat Selection & Locking** | `seat-allocation-vatsal` | Interactive seat grid with real-time selection and temporary seat locking. |
| **F05** | **Payment Gateway** | `feature/05-payment-gateway` | Secure payment processing through Razorpay test integration. |
| **F06** | **Ticket Generation & Email** | `ticket-generation-hari` | Automated PDF e-ticket generation with QR codes and email delivery via SMTP. |

> All six features are included in the [Sprint 1 integrated snapshot](sprint1/integrated/).

---

## ✨ Features (Sprint 2)

| **#** | **Feature** | **Description** |
|-------|-------------|-----------------|
| **S2-F01** | **Critics & Reviews** | Dedicated reviews page per event: write, edit and delete reviews, comments, "Helpful" votes, spoiler flag, critic vs audience separation, and AI review summaries. |
| **S2-F02** | **Browse Enhancements** | Improved search bar, new sorting options and sections on the browse page, different sections for different type of events, Change in UI, a placeholder for not loaded images in the browsing page. |
| **S2-F03** | **Venue Verification & Admin Review** | Managers submit venue details (licence, NOC, capacity) with photos and seating plans. Admins review the documents and approve or reject, with a mandatory rejection reason. |
| **S2-F04** | **Registration Security** | Birthdate field with future-date validation, confirm-password field, strong password rules, birthdate stored in Supabase, and a forgot-password fix. |
| **S2-F05** | **Organizer Verification** | Multi-step organizer application with draft saving, PAN / GSTIN / IFSC validation, and secure document uploads (private storage, versioning, signed URLs). Venue listing is now blocked until verification passes. |
| **S2-F06** | **Show Details & Flexible Venue Layouts** | Show-specific details for movies, concerts, theatre and other events. Supports cinema seats, concert stages, fan pits, standing zones and stadium layouts, with zoom, pan and hover info. Adds a Terms & Conditions tab before payment. |
| **S2-F07** | **Customer Care** | Help Centre with searchable FAQs, contact support form, My Requests with status filters, conversation threads, and an admin reply dashboard with email notifications. |
| **S2-F08** | **Ticket Cancellation & Refund** | Cancel endpoint with a 2-hour cutoff rule and Razorpay refund support. |
| **S2-F09** | **Edit Customer Profile** | Edit name, phone number, birthdate and bio, and upload or remove a profile photo. |


---

## Sprint 3 Scope

- **Dynamic pricing** — Verify the existing per-show rules and preserve the price locked when a customer holds a seat.
- **Support chatbot** — Help customers find FAQ answers and reach Customer Care.
- **Deployment** — Set up staging and document release checks.
- **Debugging and regression testing** — Fix issues and verify the end-to-end booking flow.

---

## 👥 Team & Responsibilities

### Feature Developers (Sprint 1)

| **Module / Feature** | **Responsible Members** |
|----------------------|-------------------------|
| **F01 — Authentication** | Dwij Patel · Aditya |
| **F02 — Manager Show Listing** | Rishi |
| **F03 — Browse & Search Shows** | Kavya Halani · Arpit |
| **F04 — Seat Allocation** | Khushi · Vatsal Mori |
| **F05 — Payment Gateway** | Darshan · Tirth |
| **F06 — Ticket Generation** | Hari Sharma |

### Feature Developers (Sprint 2)

| **Module / Feature** | **Responsible Members** |
|----------------------|-------------------------|
| **S2-F01 — Critics & Reviews** | Kavya · Arpit |
| **S2-F02 — Browse Enhancements** | Kavya |
| **S2-F03 — Venue Verification & Admin Review** | Dwij |
| **S2-F04 — Registration Security** | Dwij |
| **S2-F05 — Organizer Verification** | Khushi |
| **S2-F06 — Show Details & Flexible Venue Layouts** | Khushi |
| **S2-F07 — Customer Care** | Tirth · Hari |
| **S2-F08 — Ticket Cancellation & Refund** | Hari · Darshan |
| **Testing & QA** | Rishi · Vatsal |
| **Debugging & Issue Resolution** | Hari Sharma · Aditya |


### Quality Assurance & Support

| **Core Role** | **Assigned Team Members** |
|---------------|---------------------------|
| **Testing & Quality Assurance** | Vatsal Mori · Rishi |
| **Debugging & Issue Resolution** | Hari Sharma · Aditya |

---

## 📁 Repository Structure

```text
Show-Ticket-Booking-System/
│
├── .github/                          # GitHub workflows & config
├── .gitignore
├── README.md
│
├── Documentation/                    # Architecture, UML diagrams, design specs
│
├── sprint1/                          # Sprint 1 snapshot and original modules
│   ├── integrated/                  # Runnable Sprint 1 app
│   ├── database/                    # Original database schema and migrations
│   └── features/
│       ├── 01-authentication/
│       ├── 02-manager-show-listing/
│       ├── 03-browse-nearby-shows/
│       ├── 04-seat-allocation/
│       ├── 05-payment/
│       └── 06-ticket-generation/
│
├── sprint2/                          # Runnable Sprint 2 snapshot
│
└── sprint3/                          # Active integrated application
    │
    ├── backend/                      # FastAPI backend
    │   ├── fixtures/                 # Seed / test data
    │   ├── models/                   # Data models
    │   ├── routers/                  # API route handlers
    │   ├── schemas/                  # Pydantic request/response schemas
    │   ├── services/                 # Business logic (pricing, AI summary, email...)
    │   ├── tests/                    # Backend tests
    │   ├── .env.example              # Environment variable template
    │   ├── config.py
    │   ├── database.py               # asyncpg connection setup
    │   ├── dependencies.py           # Auth & shared dependencies
    │   ├── firebase_admin_setup.py
    │   ├── main.py                   # FastAPI entry point
    │   ├── requirements.txt
    │   └── Dockerfile
    │
    ├── database/                     # SQL migrations and rollback scripts
    │   ├── seeds/
    │   ├── 001_ai_review_summaries.sql
    │   ├── 003_customer_care.sql
    │   ├── 003_reviews_module.sql
    │   ├── 004_admin_verification_person_b.sql
    │   ├── 004_cancellation_refund.sql
    │   ├── 004_critics_and_reviews.sql
    │   ├── 004_organizer_verification.sql
    │   ├── 004_organizer_verification_rollback.sql
    │   ├── 004_review_deletions.sql
    │   ├── 005_review_scheduling_and_replies.sql
    │   ├── 005_venue_application_fields.sql
    │   ├── 006_fuzzy_search_pg_trgm.sql
    │   ├── 006_multi_venue_layouts.sql
    │   ├── 007_review_reports.sql
    │   ├── 007_verified_events_venues.sql
    │   ├── 008_dynamic_seat_pricing.sql
    │   ├── unified_schema.sql
    │   └── README.md
    │
    ├── frontend/                     # Next.js 14 (App Router) application
    │   ├── app/
    │   │   ├── admin/                # Admin dashboard & venue/organizer review
    │   │   ├── auth/                 # Login, register, forgot password
    │   │   ├── bookings/             # My bookings, cancellation
    │   │   ├── browse/               # Browse & search shows
    │   │   ├── events/               # Event pages & reviews
    │   │   ├── help/                 # Help Centre (FAQs)
    │   │   ├── manager/              # Manager dashboard
    │   │   ├── payment/              # Razorpay checkout
    │   │   ├── profile/              # User profile
    │   │   ├── shows/                # Seat selection
    │   │   ├── support/              # Customer Care requests
    │   │   ├── venue-verification/   # Venue verification form
    │   │   ├── verification/         # Organizer verification
    │   │   ├── globals.css
    │   │   ├── layout.tsx
    │   │   └── page.tsx
    │   ├── components/               # Reusable UI components
    │   ├── contexts/                 # React contexts (AuthContext)
    │   ├── lib/                      # API clients & helpers
    │   ├── tests/                    # Playwright tests
    │   ├── next.config.mjs
    │   ├── package.json
    │   ├── playwright.config.ts
    │   ├── postcss.config.mjs
    │   ├── tailwind.config.ts
    │   ├── tsconfig.json
    │   └── REVIEWS_INTEGRATION.md
    │
    ├── create_issues.sh
    ├── docker-compose.yml
    ├── INTEGRATION_NOTES.md
    ├── pytest.ini
    └── start-dev.sh
```

---

> **Database setup:** The base migrations are in [`sprint1/database/migrations/`](sprint1/database/migrations/). The integrated snapshots carry their own SQL additions. Review the setup notes for the selected sprint before applying changes to a database.

---

*TicketFlow — Making event discovery and ticket booking seamless.*
