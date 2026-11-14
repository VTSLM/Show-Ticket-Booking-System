# Ticket Generation Feature — Testing README

## 1. Overview

This document describes the testing strategy, test scenarios, automation, test data, and execution procedure for the **Ticket Generation & Verification** feature of the Show Ticket Booking System (`sprint1_v2`).

The Ticket Generation feature allows users and gate staff to:

- Generate ticket records idempotently for confirmed bookings (`POST /api/tickets/bookings/{booking_id}/confirm`)
- Encode scannable QR codes (`TICKETFLOW:{booking_id}`) as base64 PNGs
- Build PDF e-tickets with ReportLab including event, venue, seat breakdown, and QR code
- Stream downloadable PDF tickets from `/bookings/{bookingId}` (`GET /api/tickets/bookings/{booking_id}/pdf`)
- Dispatch HTML confirmation emails with PDF attachments via Gmail SMTP SSL (non-fatal on mail failure)
- Validate unused, used, and missing tickets (`GET /api/tickets/bookings/{booking_id}/verify`)

---

## 2. Testing Scope

### In Scope

1. Confirmed booking ticket issuance and idempotent double-click handling
2. Rejection of ticket confirmation on `pending` (unpaid) bookings
3. QR code PNG generation and payload encoding (`qr_service.py`)
4. ReportLab PDF construction for full and minimal payloads (`ticket_service.py`)
5. PDF streaming response headers (`Content-Type: application/pdf`, `Content-Disposition`)
6. Email composition, PDF attachment, and resilience when SMTP raises errors (`email_service.py`)
7. Ticket verification endpoint (`/verify`) for valid, used, missing, and malformed booking IDs
8. `/bookings` and `/bookings/[bookingId]` UI, PDF download actions, and error states (`403`/`404`/`500`)

### Out of Scope

- Razorpay order creation and payment capture (`/payment`)
- Show creation and seat layout configuration (`/manager`)
- Gate scanner hardware / camera integration

---

# 3. Testing Approach

### 3.1 Backend/API Testing

Tests `backend/routers/tickets.py`, `services/qr_service.py`, `services/ticket_service.py`, and `services/email_service.py` via FastAPI `TestClient` with `SchemaAwareFakeConn` and mocked `smtplib.SMTP_SSL`.

```text
Pytest
   ↓
FastAPI TestClient + Service Unit Tests
   ├── Tickets Router (/api/tickets/*)
   ├── QR Service (PNG generation)
   ├── Ticket Service (ReportLab PDF bytes)
   └── Email Service (Mocked SMTP_SSL)
```

### 3.2 Frontend/UI Testing

Tests `/bookings` and `/bookings/[bookingId]` independently in **Playwright** with Google Chrome (`channel: "chrome"`), using `page.route` mocks for auth and booking/PDF APIs.

### 3.3 Integration Testing

Tests real booking list retrieval and live PDF streaming (`tickets-integration.spec.ts`) without mocking `/api/bookings` or `/api/tickets/*`.

---

# 4. Tools Used

| Tool | Purpose |
|---|---|
| Pytest | Backend/API and service unit testing |
| Playwright | Frontend and integration testing (Google Chrome) |
| ReportLab & Pillow | PDF & PNG verification |
| FastAPI / Next.js | Application under test |
| TypeScript | Playwright test implementation |

---

# 5. Test File Structure

```text
sprint1_v2/
│
├── pytest.ini
├── backend/
│   └── tests/
│       ├── conftest.py
│       └── test_tickets.py
│
└── frontend/
    ├── playwright.config.ts
    └── tests/
        ├── helpers/
        │   └── mockAuth.ts
        └── tickets/
            ├── tickets.spec.ts
            ├── tickets-edge.spec.ts
            ├── tickets-integration.spec.ts
            └── tickets_test.md
```

---

# 6. Backend/API Tests

## File

```text
backend/tests/test_tickets.py
```

| Test ID | Description | Result |
|---|---|---|
| `test_tck_001` | `POST /confirm` generates ticket row and returns same `ticket_id` on retry | Passed |
| `test_tck_002` | `POST /confirm` rejects `pending` unpaid booking (`400`) | Passed |
| `test_tck_003` | `generate_qr_bytes()` produces valid PNG image | Passed |
| `test_tck_004` | `build_ticket_pdf()` outputs valid `%PDF-` bytes for full & minimal inputs | Passed |
| `test_tck_005` | `GET /pdf` streams `application/pdf` with attachment filename header | Passed |
| `test_tck_006` | Email service builds MIME+PDF attachment and `/confirm` survives SMTP failure | Passed |
| `test_tck_007` | `GET /verify` detects valid unused, used (`valid: false`), and missing tickets | Passed |
| `test_tck_008` | `GET /pdf` rejects unpaid `pending` booking instead of generating QR ticket | XFAIL (`DEF-TCK-01`) |
| `test_tck_009` | `GET /verify` handles malformed non-UUID `booking_id` gracefully | XFAIL (`DEF-TCK-02`) |

### Backend Result

```text
7 passed, 2 xfailed
```

---

# 7. Frontend/UI & Edge-Case Tests

## 7.1 `tickets.spec.ts` (Basic UI)

| Test ID | Test Scenario | Result |
|---|---|---|
| `TICKET-UI-01` | `/bookings` displays confirmed and pending bookings with `"Pay Now"` link | Passed |
| `TICKET-UI-02` | `/bookings/{id}` shows `CONFIRMED` badge, seats, total, and PDF download controls | Passed |
| `TICKET-UI-03` | Clicking `"Download Ticket PDF"` sends Bearer token and downloads `ticket_<id>.pdf` | Passed |
| `TICKET-UI-04` | Pending booking on `/bookings/{id}` shows `"Complete Payment"` instead of PDF download | Passed |

**Result: 4 passed**

---

## 7.2 `tickets-edge.spec.ts` (Edge Cases)

| Test ID | Test Scenario | Observed Result | Result |
|---|---|---|---|
| `TICKET-EDGE-01` | Empty `/bookings` list | Displays `"No bookings yet."` and `"Browse Shows"` link | Passed |
| `TICKET-EDGE-02` | Non-existent booking (`404`) | Renders `"Booking not found."` cleanly | Passed |
| `TICKET-EDGE-03` | PDF download returns HTTP `404` | Displays `"Ticket not found."` toast | Passed |
| `TICKET-EDGE-04` | PDF download returns HTTP `403` | Displays `"Authentication failed. Please log in again."` toast | Passed |
| `TICKET-EDGE-05` | PDF download returns HTTP `500` | Displays `"Could not download ticket PDF"` toast and re-enables button | Passed |

**Result: 5 passed**

---

# 8. Integration Tests

## File

```text
frontend/tests/tickets/tickets-integration.spec.ts
```

| Test ID | Description | Result |
|---|---|---|
| `TICKET-INT-01` | `/bookings` retrieves real user bookings via `GET /api/bookings` | Skipped *(credentials not set)* |
| `TICKET-INT-02` | `/bookings/{id}` downloads real `application/pdf` via `GET /api/tickets/bookings/{id}/pdf` | Skipped *(credentials/booking ID not set)* |

---

# 9. Environment Configuration

Required only for `tickets-integration.spec.ts`:

```powershell
$env:TEST_LOGIN_EMAIL="customer@example.com"
$env:TEST_LOGIN_PASSWORD="your-customer-password"
$env:TEST_CONFIRMED_BOOKING_ID="<confirmed-booking-uuid>"
```

---

# 10. Test Execution Commands

## 10.1 Backend Tests

From `sprint1_v2/`:

```bash
python -m pytest backend/tests/test_tickets.py -v
```

## 10.2 Frontend UI & Edge Tests (Playwright Chrome)

From `sprint1_v2/frontend/`:

```bash
npx playwright test tests/tickets/tickets.spec.ts tests/tickets/tickets-edge.spec.ts
```

## 10.3 Integration Tests

```bash
npx playwright test tests/tickets/tickets-integration.spec.ts --headed
```

---

# 11. Complete Ticket Generation Test Summary

| Testing Layer | Total | Passed | XFailed (Open Defects) | Failed | Skipped |
|---|---:|---:|---:|---:|---:|
| Backend/API (`pytest`) | 9 | 7 | 2 | 0 | 0 |
| Frontend/UI (`tickets.spec.ts`) | 4 | 4 | 0 | 0 | 0 |
| Frontend Edge (`tickets-edge.spec.ts`) | 5 | 5 | 0 | 0 | 0 |
| Integration (`tickets-integration.spec.ts`) | 2 | 0 | 0 | 0 | 2 |
| **Total** | **20** | **16** | **2** | **0** | **2** |

---

# 12. Application Defects Identified

### `DEF-TCK-01` — Unpaid bookings can download a valid QR ticket PDF
- **Severity:** High (`test_tck_008`)
- **File:** `sprint1_v2/backend/routers/tickets.py` (`download_ticket_pdf`)
- **Observation:** `confirm_and_generate_ticket` enforces `booking["status"] == "confirmed"`, whereas `download_ticket_pdf` omits the status check and generates/streams a full QR PDF for `'pending'` unpaid bookings.

### `DEF-TCK-02` — Malformed booking ID crashes `/verify` instead of returning invalid result
- **Severity:** Medium (`test_tck_009`)
- **File:** `sprint1_v2/backend/routers/tickets.py` (`verify_ticket`)
- **Observation:** Non-UUID strings in `GET /api/tickets/bookings/{booking_id}/verify` raise a database `DataError` instead of returning `{"valid": false, "message": "Invalid booking ID"}`.

### Additional Code Observations
- `download_ticket_pdf` omits `venue_city` from `ticket_data`, whereas emailed PDFs include it.
- `verify_ticket` is read-only (there is no check-in endpoint updating `is_used = true, used_at = now()` on gate scan) and has no staff authentication.
- `payment/page.tsx` wraps `await ticketsApi.confirm(bookingId)` in `try {} catch {}` and displays `"Payment successful! Ticket emailed to you."` even if ticket creation fails.

---

# 13. Testing Conclusion

All **16 core frontend UI, edge, PDF/QR/email service, and backend tests** passed (`7/9` backend with `2` expected defect xfails, `9/9` Playwright UI & edge tests in Chrome, `2` live-integration skipped without live credentials).

