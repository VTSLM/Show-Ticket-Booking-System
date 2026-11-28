# TicketFlow Object Design — Submission Exports

This directory contains the academic submission deliverables for the **IT314 Software Engineering** Object Design Documentation.

## Contents

| File / Directory | Description |
|---|---|
| `TicketFlow_Object_Design.pdf` | Consolidated academic Object Design report with all 31 UML diagrams embedded across portrait and landscape pages |
| `diagrams/` | Individual high-resolution diagram exports (31 `.png` files) |

## Diagram Inventory (31 PNGs)

### Architecture, Subsystems, Packages & Components (6)
- `architecture.png` — Four-tier system architecture with external cloud services
- `subsystem-decomposition.png` — 14 functional subsystems with dependencies
- `backend-packages.png` — FastAPI backend package structure
- `frontend-packages.png` — Next.js 14 App Router package structure
- `component-diagram.png` — UML Component diagram with provided/required interfaces
- `component-booking-payment.png` — Booking & Payment subsystem detail view

### Class Diagrams (7)
- `class-users.png` — Users, Roles, Sessions, OrganizerProfile, BankAccount
- `class-events-venues.png` — Venues, Screens, Seats, Events, Shows, ShowSeats, ShowZones
- `class-booking-payment.png` — Bookings, Payments, Receipts, Coupons, CancellationPolicy
- `class-tickets-transfers.png` — Tickets, Transfers, TransferSeats, DemoPayments
- `class-reviews.png` — Reviews, Comments, Upvotes, Versions, Reports, AI Summaries
- `class-verification.png` — Organizer KYC and Venue Compliance verification models
- `class-support-admin.png` — Notifications, Support, Audit Logs, Terms

### Sequence Diagrams (8)
- `sequence-booking.png` — Customer seat selection through ticket issuance
- `sequence-seat-locking.png` — Two-user concurrency race condition resolution
- `sequence-cancellation-refund.png` — Cancellation eligibility, Razorpay refund, seat release
- `sequence-ticket-transfer.png` — P2P transfer initiation, email claim, QR reissuance
- `sequence-organizer-verification.png` — KYC case lifecycle with risk scoring
- `sequence-venue-verification.png` — Venue compliance submission and admin review
- `sequence-review.png` — Review submission with AI sentiment summarization
- `sequence-authentication.png` — Firebase token exchange, session validation, inactivity logout

### State Machine Diagrams (8)
- `state-booking.png` — Booking lifecycle (`pending` → `confirmed`/`cancelled`/`expired`)
- `state-seat.png` — ShowSeat lifecycle (`available` ↔ `locked` → `booked`/`reserved`)
- `state-payment.png` — Payment lifecycle (`created` → `successful`/`failed` → `refunded`)
- `state-ticket.png` — Ticket lifecycle (`valid` → `used`/`cancelled`)
- `state-ticket-transfer.png` — Transfer lifecycle (`pending` → `accepted`/`declined`/`cancelled`/`expired`)
- `state-organizer-verification.png` — KYC verification workflow states
- `state-venue-verification.png` — Venue compliance workflow states
- `state-refund.png` — Refund lifecycle (`PENDING` → `PROCESSED`/`FAILED`)

### Activity Diagrams (2)
- `activity-customer-booking.png` — End-to-end booking workflow with 6 swimlanes
- `activity-cancellation.png` — Cancellation and refund workflow with swimlanes
