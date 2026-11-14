# Payment Gateway Feature — Testing README

## 1. Overview

This document describes the testing strategy, test scenarios, automation, test data, and execution procedure for the **Payment Gateway** feature of the Show Ticket Booking System (`sprint1_v2`).

The Payment Gateway feature allows authenticated users to:

- Review pending booking summaries on `/payment?booking_id=...`
- Create Razorpay orders in INR paise (`POST /api/payments/orders`)
- Complete checkout in Razorpay and handle modal dismissal
- Verify HMAC-SHA256 payment signatures (`POST /api/payments/orders/{booking_id}/verify`)
- Atomically confirm bookings, convert locked seats to `booked`, record payments, and generate receipts
- Access completed booking states and download PDFs after payment

The testing covers the backend API, frontend UI, edge cases, and frontend-to-backend integration.

---

## 2. Testing Scope

### In Scope

1. Pending booking retrieval and summary display on `/payment`
2. Razorpay order creation and INR-to-paise conversion
3. Rejection of non-pending / already confirmed bookings (`400 Bad Request`)
4. HMAC-SHA256 signature verification and tamper rejection
5. Atomic commit across `payment_orders`, `bookings`, `show_seats`, `payments`, and `receipts`
6. Modal dismissal (`ondismiss`), order creation failure, and verification error recovery
7. Receipt lookup endpoint (`GET /api/payments/receipts/{receipt_number}`) and ownership isolation
8. Frontend-to-backend integration tests

### Out of Scope

- Venue/show creation (`/manager`)
- Customer seat locking before booking creation (`/shows/[id]/seats`)
- Actual live bank/UPI money transfer outside Razorpay Test Mode

---

# 3. Testing Approach

### 3.1 Backend/API Testing

Tests `backend/routers/payments.py` via FastAPI `TestClient` with `SchemaAwareFakeConn` (enforcing `001_initial_schema.sql` and `002_payment_gateway.sql` constraints, including `uq_one_unresolved_payment_order_per_booking` and the `receipts` foreign-key schema) and mocked `razorpay.Client`.

```text
Pytest
   ↓
FastAPI TestClient
   ↓
Payments Router (/api/payments/*)
   ↓
Mocked Razorpay Client + Schema-Aware Fake AsyncPG
```

### 3.2 Frontend/UI Testing

Tests `/payment` independently in **Playwright** with Google Chrome (`channel: "chrome"`).

`https://checkout.razorpay.com/v1/checkout.js` and `/api/payments/*` are mocked via `page.route` to deterministically test payment success, modal dismissal, and invalid-signature handling offline.

### 3.3 Integration Testing

Tests `/payment` against real FastAPI + Supabase + Razorpay Test Mode (`payment-integration.spec.ts`) without mocking Payment APIs.

---

# 4. Tools Used

| Tool | Purpose |
|---|---|
| Pytest | Backend/API testing |
| Playwright | Frontend and integration testing (Google Chrome) |
| FastAPI | Backend API |
| Next.js | Frontend |
| Razorpay Python SDK & Checkout JS | Payment integration |
| Supabase/PostgreSQL | Persistence |

---

# 5. Test File Structure

```text
sprint1_v2/
│
├── pytest.ini
├── backend/
│   └── tests/
│       ├── conftest.py
│       └── test_payments.py
│
└── frontend/
    ├── playwright.config.ts
    └── tests/
        ├── helpers/
        │   └── mockAuth.ts
        └── payment/
            ├── payment.spec.ts
            ├── payment-edge.spec.ts
            ├── payment-integration.spec.ts
            └── payment_test.md
```

---

# 6. Backend/API Tests

## File

```text
backend/tests/test_payments.py
```

| Test ID | Description | Result |
|---|---|---|
| `test_pay_001` | Create Razorpay order converts ₹500.00 to `50000` paise | Passed |
| `test_pay_002` | Reject order creation for confirmed booking (`400`) | Passed |
| `test_pay_003` | Valid HMAC signature confirms booking, books seats, inserts payment & receipt | Passed |
| `test_pay_004` | Forged HMAC-SHA256 signature rejected (`400 Invalid payment signature`) | Passed |
| `test_pay_005` | Retrying `POST /orders` on same pending booking hits unresolved-order unique index | XFAIL (`DEF-PAY-03`) |
| `test_pay_006` | `19.99` INR converts to `1998` instead of `1999` paise due to `int(float * 100)` | XFAIL (`DEF-PAY-04`) |
| `test_pay_007` | Cross-user `POST /verify` on another user's booking is not blocked | XFAIL (`DEF-PAY-02`) |
| `test_pay_008` | `GET /receipts/{receipt_number}` crashes querying non-existent `r.booking_id` | XFAIL (`DEF-PAY-01`) |

### Backend Result

```text
4 passed, 4 xfailed
```

---

# 7. Frontend/UI & Edge-Case Tests

## 7.1 `payment.spec.ts` (Basic UI)

| Test ID | Test Scenario | Result |
|---|---|---|
| `PAY-UI-01` | Pending booking renders seats, status, total (`₹500.00`), and Pay button | Passed |
| `PAY-UI-02` | Pay creates order, verifies payment, calls ticket confirm, redirects to `/bookings/{id}` | Passed |
| `PAY-UI-03` | Confirmed booking displays `"Payment already completed!"` and Download PDF button | Passed |
| `PAY-UI-04` | Confirmed `/payment` screen streams and downloads `ticket_<id>.pdf` | Passed |

**Result: 4 passed**

---

## 7.2 `payment-edge.spec.ts` (Edge Cases)

| Test ID | Test Scenario | Observed Result | Result |
|---|---|---|---|
| `PAY-EDGE-01` | Unauthenticated user opens `/payment` | Displays `"Please log in to continue."` with `/auth/login` link | Passed |
| `PAY-EDGE-02` | Missing booking ID (`404`) | Displays `"Booking not found."` cleanly | Passed |
| `PAY-EDGE-03` | User dismisses Razorpay modal (`ondismiss`) | Pay button recovers and stays enabled | Passed |
| `PAY-EDGE-04` | `POST /orders` returns `400` error | Error toast shown; Pay button re-enabled | Passed |
| `PAY-EDGE-05` | `POST /verify` returns `400 Invalid payment signature` | Error toast displayed; remains on `/payment` | Passed |
| `PAY-EDGE-06` | Direct `page.goto` / browser refresh on `/payment` | Fails because `useEffect` calls `bookingsApi.get` before `AuthContext` restores user | Expected Fail (`DEF-PAY-05`) |

**Result: 5 passed, 1 expected-fail (`test.fail`)**

---

# 8. Integration Tests

## File

```text
frontend/tests/payment/payment-integration.spec.ts
```

| Test ID | Description | Result |
|---|---|---|
| `PAY-INT-01` | Real pending booking fetched via `GET /api/bookings/{id}` | Skipped *(credentials/booking ID not set)* |
| `PAY-INT-02` | Clicking Pay calls live `POST /api/payments/orders` in Razorpay Test Mode | Skipped *(credentials/booking ID not set)* |

---

# 9. Environment Configuration

Required only for `payment-integration.spec.ts`:

```powershell
$env:TEST_LOGIN_EMAIL="customer@example.com"
$env:TEST_LOGIN_PASSWORD="your-customer-password"
$env:TEST_PENDING_BOOKING_ID="<pending-booking-uuid>"
```

---

# 10. Test Execution Commands

## 10.1 Backend Tests

From `sprint1_v2/`:

```bash
python -m pytest backend/tests/test_payments.py -v
```

## 10.2 Frontend UI & Edge Tests (Playwright Chrome)

From `sprint1_v2/frontend/`:

```bash
npx playwright test tests/payment/payment.spec.ts tests/payment/payment-edge.spec.ts
```

## 10.3 Integration Tests

```bash
npx playwright test tests/payment/payment-integration.spec.ts --headed
```

---

# 11. Complete Payment Gateway Test Summary

| Testing Layer | Total | Passed | Expected Fail (`xfail`/`test.fail`) | Failed | Skipped |
|---|---:|---:|---:|---:|---:|
| Backend/API (`pytest`) | 8 | 4 | 4 | 0 | 0 |
| Frontend/UI (`payment.spec.ts`) | 4 | 4 | 0 | 0 | 0 |
| Frontend Edge (`payment-edge.spec.ts`) | 6 | 5 | 1 | 0 | 0 |
| Integration (`payment-integration.spec.ts`) | 2 | 0 | 0 | 0 | 2 |
| **Total** | **20** | **13** | **5** | **0** | **2** |

---

# 12. Application Defects Identified

### `DEF-PAY-01` — Receipt lookup crashes (`r.booking_id` does not exist)
- **Severity:** Critical (`test_pay_008`)
- **File:** `sprint1_v2/backend/routers/payments.py` (`get_receipt`)
- **Observation:** `001_initial_schema.sql` defines `receipts` with `payment_id` referencing `payments(id)` and no `booking_id` column, causing `JOIN bookings b ON b.id=r.booking_id` to fail at runtime.

### `DEF-PAY-02` — Payment verification lacks user ownership and order-to-booking checks
- **Severity:** Critical Security (`test_pay_007`)
- **File:** `sprint1_v2/backend/routers/payments.py` (`verify_payment`)
- **Observation:** `verify_payment` checks the HMAC signature but does not confirm that `bookings.user_id == current_user["id"]`, that `booking.status == 'pending'`, or that `req.razorpay_order_id` was issued for that `booking_id`.

### `DEF-PAY-03` — Payment retry fails after modal dismissal
- **Severity:** High (`test_pay_005`)
- **Files:** `sprint1_v2/backend/routers/payments.py` (`create_order`), `002_payment_gateway.sql`
- **Observation:** `create_order` only catches `ON CONFLICT (razorpay_order_id)`, colliding with the partial unique index `uq_one_unresolved_payment_order_per_booking` if a user re-clicks Pay on the same pending booking.

### `DEF-PAY-04` — Float truncation loses 1 paisa on decimal amounts
- **Severity:** Major (`test_pay_006`)
- **File:** `sprint1_v2/backend/routers/payments.py` (`create_order`)
- **Observation:** `int(float("19.99") * 100)` evaluates to `1998` instead of `1999`. Use `round()` / `Decimal`.

### `DEF-PAY-05` — Direct visit / refresh on `/payment` fails auth check before Firebase loads
- **Severity:** High (`PAY-EDGE-06`)
- **File:** `sprint1_v2/frontend/app/payment/page.tsx`
- **Observation:** `useEffect` calls `bookingsApi.get(bookingId)` immediately without waiting for `useAuth()` (`user` / `authLoading`), causing `getToken()` to throw `"Not authenticated"` on page reload and display `"Booking not found."`.

*(Additional UI note: In `payment/page.tsx`, the error `catch` inside Razorpay `handler` omits `setPaying(false)`, leaving the Pay button stuck disabled if verification fails.)*

---

# 13. Testing Conclusion

All happy-path payment UI flows (**13 passing checks**) verified order creation, Razorpay callback wiring, HMAC verification, modal dismissal recovery, and post-payment PDF downloads, while backend and edge testing surfaced **5 critical/high integration defects (`DEF-PAY-01`–`DEF-PAY-05`)** that must be fixed before production checkout.

