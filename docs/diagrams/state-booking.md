# State Machine Diagram: Booking Lifecycle

## 1. Description and Purpose
Following UML State Machine conventions (Lecture 23, UML State Diagram), this diagram models the lifecycle of a `Booking` entity. States, triggers, guard conditions, and actions are derived strictly from the PostgreSQL `booking_status` enum, CHECK constraints, and backend logic in `backend/routers/bookings.py`, `backend/routers/payments.py`, and `backend/routers/cancellations.py`.

## 2. State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> pending: Customer creates booking [seats locked] / do create_booking()

    state pending {
        [*] --> awaiting_payment: Payment order generated
        awaiting_payment --> awaiting_payment: Apply coupon / recalculate total
    }

    pending --> confirmed: Payment verified via HMAC / emit_tickets(), record_payment()
    pending --> expired: Payment timer expired (10m) / release_seat_locks()
    pending --> cancelled: Customer aborts checkout / release_seat_locks()

    state confirmed {
        [*] --> active_booking: Tickets valid for show entry
        active_booking --> active_booking: Peer-to-peer ticket transfer initiated
    }

    confirmed --> cancelled: Customer cancels booking [within policy cutoff] / initiate_refund(), release_seats()
    confirmed --> [*]: Show completed & tickets scanned at gate

    cancelled --> [*]: Terminal state (refund processed or fee deducted)
    expired --> [*]: Terminal state (seats released to inventory)
```

## 3. State Definitions and Transition Table
| Source State | Event / Trigger | Guard Condition | Target State | Actions / Effects |
|---|---|---|---|---|
| `[*]` | Checkout initiated | Seats locked by current user | `pending` | `INSERT INTO bookings (status='pending')`, record line items |
| `pending` | Payment verified | Valid HMAC signature from Razorpay | `confirmed` | `UPDATE bookings SET status='confirmed'`, generate tickets, send email |
| `pending` | Timer expiry | `locked_until < NOW()` | `expired` | `UPDATE bookings SET status='expired'`, release held seats |
| `pending` | User cancellation | Explicit cancel before payment | `cancelled` | Reset held seat locks to `available` |
| `confirmed` | Cancellation requested | Show time $-$ NOW() $\ge$ policy cutoff hours | `cancelled` | Record refund, reset show seats to `available`, cancel tickets |
| `confirmed` | Event date passed | Show completed | `[*]` | Mark booking fulfilled |

## 4. Source Traceability
- Enum: `booking_status ('pending', 'confirmed', 'cancelled', 'expired')` in `database/migrations/0001_initial_schema.sql`.
- Code: `backend/routers/bookings.py`, `backend/routers/payments.py`, `backend/routers/cancellations.py`.
