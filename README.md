
# TicketFlow — Show Ticket Booking System

> **IT314 Software Engineering** · **DA-IICT** · **Batch 2024** · **Sprint 1 (Under Active Development)**

TicketFlow is a modern, full-stack event ticketing platform developed as a university software engineering project. It provides an end-to-end event management and ticketing solution where users can discover upcoming events, select and lock seats in real time, make secure online payments via Razorpay, and receive instant e-tickets with scannable QR codes.

Venue managers can list and schedule events, while administrators manage access control and platform operations.

> **Status:** This repository represents Sprint 1 deliverables and is currently under active development.

---

## 🚧 Active Development Branch

> **All current development and active code integration are happening on the [`integration/feature-merging`](../../tree/integration/feature-merging) branch.**

This `main` branch serves as the initial project skeleton. The complete working, integrated codebase — featuring all 6 Sprint 1 modules, the unified FastAPI backend, and the Next.js frontend — lives on:

```bash
integration/feature-merging
```

To view, test, or run the application locally, switch to the active development branch:

```bash
git checkout integration/feature-merging
```

The complete project documentation, including setup instructions, environment variables, database schema, API endpoints, and known issues, is available in the [README on the active development branch](../../blob/integration/feature-merging/README.md).

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

> All 6 features are merged and fully integrated on the `integration/feature-merging` branch.

---

## 👥 Team & Responsibilities

### Feature Developers

| **Module / Feature** | **Responsible Members** |
|----------------------|-------------------------|
| **F01 — Authentication** | Dwij Patel · Aditya |
| **F02 — Manager Show Listing** | Rishi |
| **F03 — Browse & Search Shows** | Kavya Halani · Arpit |
| **F04 — Seat Allocation** | Khushi · Vatsal Mori |
| **F05 — Payment Gateway** | Darshan · Tirth |
| **F06 — Ticket Generation** | Hari Sharma |

### Quality Assurance & Support

| **Core Role** | **Assigned Team Members** |
|---------------|---------------------------|
| **Testing & Quality Assurance** | Vatsal Mori · Rishi |
| **Debugging & Issue Resolution** | Hari Sharma · Aditya |

---

## 📁 Repository Structure

```text
ticketflow/
│
├── sprint1/                         # Individual feature modules (pre-integration)
│   └── features/
│       ├── 01-authentication/
│       ├── 02-manager-show-listing/
│       ├── 03-browse-shows/
│       ├── 04-seat-allocation/
│       ├── 05-payment/
│       └── 06-ticket-generation/
│
├── sprint1_v2/                      # Unified integrated codebase (Primary target)
│   │
│   ├── backend/                     # FastAPI backend integrating all 6 features
│   │
│   └── frontend/                    # Next.js 14 App Router application
│
└── Documentation/                   # Software architecture, UML diagrams,
                                     # and design specifications
```

---

> **Note:** For complete setup instructions, environment configuration, database schema, API documentation, and known issues, refer to the [full project README on `integration/feature-merging`](../../blob/integration/feature-merging/README.md).

---

*TicketFlow — Making event discovery and ticket booking seamless.*
