# TicketFlow — Show Ticket Booking System

> IT314 Software Engineering · DA-IICT · Batch 2024 · Sprint 1

A full-stack event ticketing platform built as a university software engineering project. Users can browse shows, select seats, pay via Razorpay, and download e-tickets with QR codes. Venue managers can create and schedule events. Admins approve managers and manage the platform.

---

## 🚧 Active Development Branch

> **All current development is happening on the [`integration/feature-merging`](../../tree/integration/feature-merging) branch.**

This `main` branch contains the initial project skeleton. The working, integrated codebase — including all 6 Sprint 1 features, the unified FastAPI backend, and the Next.js frontend — lives on:

```
integration/feature-merging
```

To view or run the project, switch to that branch:

```bash
git checkout integration/feature-merging
```

The full project documentation (setup instructions, database schema, API reference, team, known issues) is in the [README on that branch](../../blob/integration/feature-merging/README.md).

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

## Features (Sprint 1)

| # | Feature | Branch |
|---|---------|--------|
| F01 | User Authentication (Firebase) | `login` |
| F02 | Manager Show Listing | `managers-can-list` |
| F03 | Browse & Search Shows | `browse-nearby-shows` |
| F04 | Seat Selection & Locking | `seat-allocation-vatsal` |
| F05 | Payment Gateway (Razorpay) | `feature/05-payment-gateway` |
| F06 | Ticket Generation & Email Delivery | `ticket-generation-hari` |

All 6 features are merged and integrated on `integration/feature-merging`.

---

## Team

| Member | Feature |
|--------|---------|
| Vatsal Mori | F04 — Seat Allocation |
| Hari Sharma | F06 — Ticket Generation · Integration Lead |
| Darshan | F03 — Browse Shows |
| Janak / Arpit | F01 — Authentication |
| Dwij Patel | F05 — Payment Gateway |
| Khushi | F02 — Manager Show Listing |

---

## Repository Structure

```
ticketflow/
├── sprint1/           # Individual feature branches (pre-integration)
│   └── features/
│       ├── 01-authentication/
│       ├── 02-manager-show-listing/
│       ├── 03-browse-shows/
│       ├── 04-seat-allocation/
│       ├── 05-payment/
│       └── 06-ticket-generation/
├── sprint1_v2/        # Unified integrated codebase ← start here
│   ├── backend/       # Single FastAPI app (all 6 features)
│   └── frontend/      # Next.js 14 (App Router)
└── Documentation/     # UML diagrams, design docs
```

> For setup instructions, database schema, and API reference — see the full README on [`integration/feature-merging`](../../blob/integration/feature-merging/README.md).
