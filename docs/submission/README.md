# TicketFlow Object Design — Submission Exports

This directory contains the academic submission deliverables for the **IT314 Software Engineering** Object Design Documentation at DA-IICT.

## Contents

| File / Directory | Description |
|---|---|
| `TicketFlow_Object_Design.pdf` | 37-page consolidated academic report with all 31 UML diagrams embedded |
| `diagrams/` | Individual diagram exports (31 SVG + 31 PNG files) |

## Diagram Inventory (31 diagrams)

### Architecture & Structure (5)
| File | Description |
|---|---|
| `architecture` | Four-tier system architecture with external cloud services |
| `subsystem-decomposition` | 14 functional subsystems with dependencies |
| `backend-packages` | FastAPI backend package structure |
| `frontend-packages` | Next.js 14 App Router package structure |
| `component-diagram` | UML Component diagram with provided/required interfaces |

### Additional Component View (1)
| File | Description |
|---|---|
| `component-booking-payment` | Booking & Payment subsystem detail view |

### Class Diagrams (7)
| File | Description |
|---|---|
| `class-users` | Users, Roles, Sessions, OrganizerProfile, BankAccount |
| `class-events-venues` | Venues, Screens, Seats, Events, Shows, ShowSeats, ShowZones |
| `class-booking-payment` | Bookings, Payments, Receipts, Coupons, CancellationPolicy |
| `class-tickets-transfers` | Tickets, Transfers, TransferSeats, DemoPayments |
| `class-reviews` | Reviews, Comments, Upvotes, Versions, Reports, AI Summaries |
| `class-verification` | Organizer KYC and Venue Compliance verification models |
| `class-support-admin` | Notifications, Support, Audit Logs, Terms |

### Sequence Diagrams (8)
| File | Description |
|---|---|
| `sequence-booking` | Customer seat selection through ticket issuance |
| `sequence-seat-locking` | Two-user concurrency race condition resolution |
| `sequence-cancellation-refund` | Cancellation eligibility, Razorpay refund, seat release |
| `sequence-ticket-transfer` | P2P transfer initiation, email claim, QR reissuance |
| `sequence-organizer-verification` | KYC case lifecycle with risk scoring |
| `sequence-venue-verification` | Venue compliance submission and admin review |
| `sequence-review` | Review submission with AI sentiment summarization |
| `sequence-authentication` | Firebase token exchange, session validation, inactivity logout |

### State Machine Diagrams (8)
| File | Description |
|---|---|
| `state-booking` | Booking lifecycle (pending → confirmed/cancelled/expired) |
| `state-seat` | ShowSeat lifecycle (available ↔ locked → booked/reserved) |
| `state-payment` | Payment lifecycle (created → successful/failed → refunded) |
| `state-ticket` | Ticket lifecycle (valid → used/cancelled) |
| `state-ticket-transfer` | Transfer lifecycle (pending → accepted/declined/cancelled/expired) |
| `state-organizer-verification` | KYC verification workflow states |
| `state-venue-verification` | Venue compliance workflow states |
| `state-refund` | Refund lifecycle (PENDING → PROCESSED/FAILED) |

### Activity Diagrams (2)
| File | Description |
|---|---|
| `activity-customer-booking` | End-to-end booking workflow with 6 swimlanes |
| `activity-cancellation` | Cancellation and refund workflow with swimlanes |

## How to Regenerate

### Prerequisites
- Node.js 20+ with npx
- Python 3.12+ with `reportlab` and `Pillow`

### Render diagrams (SVG + PNG)
```bash
# From the repository root
npx @mermaid-js/mermaid-cli -i docs/diagrams/<name>.md -o docs/submission/diagrams/<name>.svg -b white
npx @mermaid-js/mermaid-cli -i docs/diagrams/<name>.md -o docs/submission/diagrams/<name>.png -b white -s 2
```

Or use the batch render script:
```bash
python scratch/render_all.py
```

### Generate PDF
```bash
python scratch/generate_pdf.py
```

## Source Documentation
The original Mermaid diagram sources are preserved in:
- `docs/object-design.md` — Master specification document
- `docs/diagrams/*.md` — 30 individual diagram files with Mermaid code and explanations

These Markdown files are the source of truth. The exports in this directory are generated artifacts.
