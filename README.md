# TicketFlow - Show Ticket Booking System

> **IT314 Software Engineering** · **DA-IICT** · **Batch 2024** · **Sprint 1 & Sprint 2 snapshots · Sprint 3 active**

TicketFlow is a modern, full-stack event ticketing platform developed as a university software engineering project. It provides an end-to-end event management and ticketing solution where users can discover upcoming events, select and lock seats in real time, make secure online payments via Razorpay, and receive instant e-tickets with scannable QR codes.

Venue managers can list and schedule events, while administrators manage access control and platform operations.

> **Status:** One app at the repo root. Earlier sprints are tagged: [v0.1.0 (Sprint 1)](https://github.com/VTSLM/Show-Ticket-Booking-System/releases/tag/v0.1.0), [v0.2.0 (Sprint 2)](https://github.com/VTSLM/Show-Ticket-Booking-System/releases/tag/v0.2.0).

---

## Run Locally

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`, fill in the team's test values, then run these in two terminals from the repo root (or use `./scripts/dev.sh`).

**Backend**

```sh
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

**Frontend**

```sh
cd frontend
npm ci
npm run dev
```

Open [TicketFlow locally](http://localhost:3000). The API docs are at http://localhost:8000/docs.

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

> All six features are included in [v0.1.0](https://github.com/VTSLM/Show-Ticket-Booking-System/releases/tag/v0.1.0).

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
├── backend/        # FastAPI app (routers, services, schemas, tests)
├── frontend/       # Next.js 14 app (App Router, Tailwind, Playwright tests)
├── database/       # Ordered SQL migrations, rollbacks, seeds
├── infra/          # Terraform for Azure (planned)
├── docs/           # Requirements PDFs and historical notes
├── scripts/        # Developer scripts (dev.sh)
├── docker-compose.yml
└── .github/        # CI workflows
```

---

> **Database setup:** see [database/README.md](database/README.md).

---

*TicketFlow — Making event discovery and ticket booking seamless.*
