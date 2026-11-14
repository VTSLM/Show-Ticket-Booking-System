# Seat Selection Testing

## 1. Overview

This document describes the testing performed for the **Seat Selection** feature of the Show Ticket Booking System.

The Seat Selection feature allows users to:

- View the seat map for a show.
- Identify available, locked, booked, reserved, and premium seats.
- Select available seats.
- Lock selected seats temporarily.
- Release selected seats.
- Calculate the total ticket price.
- Proceed to the booking/payment flow.
- Handle unavailable seats and API failures.

Testing was performed at three levels:

1. **Backend/API Testing** using Pytest.
2. **Frontend/UI and Edge-Case Testing** using Playwright.
3. **Frontend–Backend Integration Testing** using Playwright with the real backend and database.

---

# 2. Test Scenarios

The following scenarios were identified for the Seat Selection feature.

## 2.1 Seat Map

| ID | Test Scenario |
|---|---|
| SEAT-UI-01 | Verify that the seat-selection page loads successfully. |
| SEAT-UI-02 | Verify that seats are displayed in their respective rows. |
| SEAT-INT-01 | Verify that the real seat map is retrieved from the backend. |
| SEAT-EDGE-01 | Verify that an empty seat map is handled correctly. |

## 2.2 Seat Selection

| ID | Test Scenario |
|---|---|
| SEAT-UI-03 | Verify that an available seat can be selected. |
| SEAT-UI-04 | Verify that multiple available seats can be selected. |
| SEAT-UI-05 | Verify that the total price is calculated correctly. |
| SEAT-UI-06 | Verify that premium seats use their own price. |
| SEAT-UI-10 | Verify that a selected seat can be deselected. |
| SEAT-UI-11 | Verify that the payment button appears after seat selection. |

## 2.3 Unavailable Seats

| ID | Test Scenario |
|---|---|
| SEAT-UI-07 | Verify that booked seats cannot be selected. |
| SEAT-UI-08 | Verify that locked seats cannot be selected. |
| SEAT-UI-09 | Verify that reserved seats cannot be selected. |
| SEAT-INT-04 | Verify that unavailable seats received from the real backend cannot be selected. |

## 2.4 Seat Locking and Releasing

| ID | Test Scenario |
|---|---|
| SEAT-EDGE-03 | Verify that seat locking failure is handled. |
| SEAT-EDGE-04 | Verify that an unavailable seat cannot be locked. |
| SEAT-INT-02 | Verify that an available seat can be locked through the real backend. |
| SEAT-INT-03 | Verify that a selected seat can be released through the real backend. |

## 2.5 Booking Flow

| ID | Test Scenario |
|---|---|
| SEAT-EDGE-05 | Verify that the booking/payment flow is available after seat selection. |
| SEAT-EDGE-06 | Verify that the user cannot proceed without selecting a seat. |
| SEAT-INT-05 | Verify that the booking endpoint is reached after successful seat selection. |

## 2.6 Error Handling

| ID | Test Scenario |
|---|---|
| SEAT-EDGE-02 | Verify that a seat-map API failure is handled gracefully. |

---

# 3. What Was Automated

## 3.1 Backend/API Tests

Backend testing was performed using **Pytest**.

### `backend/tests/test_seats.py`

This file contains tests for:

- Retrieving the seat map.
- Handling expired seat locks.
- Locking an available seat.
- Locking multiple seats.
- Rejecting an empty seat list.
- Rejecting unavailable seats.
- Rolling back a partial lock failure.
- Releasing a locked seat.
- Releasing multiple seats.

**Result: 9/9 tests passed.**

### `backend/tests/test_bookings.py`

This file contains tests for:

- Creating a booking with locked seats.
- Calculating the booking total from seat prices.
- Rejecting nonexistent seats.
- Rejecting unlocked seats.
- Rejecting seats locked by another user.
- Creating bookings with multiple seats.

**Result: 6/6 tests passed.**

### Backend total

**15/15 tests passed.**

---

# 4. Frontend UI and Edge-Case Testing

Frontend testing was performed using **Playwright**.

## 4.1 Basic Seat Selection Tests

File:

```text
frontend/tests/seats/seat-selection.spec.ts
```

The tests cover:

- Seat-selection page loading.
- Seat-row rendering.
- Available seat selection.
- Multiple seat selection.
- Total-price calculation.
- Premium-seat pricing.
- Booked-seat restrictions.
- Locked-seat restrictions.
- Reserved-seat restrictions.
- Seat deselection.
- Payment-button visibility.

These tests also helped identify an authentication-state issue affecting seat selection.

---

# 5. Edge-Case Testing

File:

```text
frontend/tests/seats/seat-selection-edge.spec.ts
```

The following edge cases were tested:

### SEAT-EDGE-01
**Empty seat map is handled**

Result:

**PASS**

The application displays:

```text
No seats are currently available for this show.
```

### SEAT-EDGE-02
**Seat map API failure is handled**

Result:

**PASS**

The seat-map API was intentionally made to return HTTP 500.

The application handled the failure without crashing and displayed the empty-seat fallback state.

### SEAT-EDGE-03
**Seat locking is handled**

Result:

**BLOCKED**

The test cannot reach the locking operation because the authenticated user is incorrectly treated as unauthenticated on the Seat Selection page.

### SEAT-EDGE-04
**Unavailable-seat locking is handled**

Result:

**BLOCKED**

The test is blocked by the same authentication-state issue before the locking operation can be reached.

### SEAT-EDGE-05
**Booking/payment flow is handled**

Result:

**BLOCKED**

The test cannot reach the booking flow because a seat cannot be selected due to the authentication issue.

### SEAT-EDGE-06
**User cannot proceed without selecting a seat**

Result:

**PASS**

---

## Edge-Case Summary

| Test | Result |
|---|---|
| SEAT-EDGE-01 | PASS |
| SEAT-EDGE-02 | PASS |
| SEAT-EDGE-03 | BLOCKED |
| SEAT-EDGE-04 | BLOCKED |
| SEAT-EDGE-05 | BLOCKED |
| SEAT-EDGE-06 | PASS |

**3 passed, 3 blocked by the same application defect.**

---

# 6. Integration Testing

Integration testing verifies the interaction between:

```text
Next.js Frontend
       ↓
FastAPI Backend
       ↓
PostgreSQL / Supabase Database
```

Unlike the UI tests, the seat APIs were **not mocked** during integration testing.

File:

```text
frontend/tests/seats/seat-selection-integration.spec.ts
```

## SEAT-INT-01 — Real Seat Map

The test verifies that:

1. The Seat Selection page requests the real seat map API.
2. The backend responds successfully.
3. The response contains actual seat data.
4. The seats are rendered in the frontend.

**Result: PASS**

---

## SEAT-INT-02 — Lock Available Seat

The test attempts to:

1. Log in.
2. Open the Seat Selection page.
3. Select an available seat.
4. Send a real request to:

```text
POST /api/seats/{show_id}/lock
```

**Result: BLOCKED / APPLICATION DEFECT**

The user is redirected to:

```text
/auth/login
```

and the application displays:

```text
Please log in first
```

The `/lock` API is never reached.

---

## SEAT-INT-03 — Release Selected Seat

The test attempts to:

1. Select an available seat.
2. Lock it through the real backend.
3. Deselect the seat.
4. Release it through the real backend.

**Result: BLOCKED**

The test cannot reach the locking/releasing stage because of the same authentication-state problem.

---

## SEAT-INT-04 — Unavailable Seat

The test verifies that unavailable seats returned by the real backend are disabled in the frontend.

**Result: PASS**

---

## SEAT-INT-05 — Booking Integration

The test attempts to:

1. Select an available seat.
2. Lock the seat.
3. Click **Proceed to Payment**.
4. Send a request to:

```text
POST /api/bookings
```

5. Verify the booking response.

**Result: BLOCKED**

The seat cannot be selected because of the authentication-state defect.

---

## Integration Summary

| Test | Result |
|---|---|
| SEAT-INT-01 | PASS |
| SEAT-INT-02 | BLOCKED |
| SEAT-INT-03 | BLOCKED |
| SEAT-INT-04 | PASS |
| SEAT-INT-05 | BLOCKED |

**2 passed, 3 blocked by the same application defect.**

---

# 7. Application Defect Identified

## Bug: Authenticated user is redirected to Login when selecting an available seat

### Severity

**High**

### Priority

**High**

### Feature

**Seat Selection / Authentication Integration**

### Affected Tests

- SEAT-UI-03
- SEAT-UI-04
- SEAT-UI-05
- SEAT-UI-06
- SEAT-UI-10
- SEAT-UI-11
- SEAT-EDGE-03
- SEAT-EDGE-04
- SEAT-EDGE-05
- SEAT-INT-02
- SEAT-INT-03
- SEAT-INT-05

### Observed Behavior

An authenticated user can access the Seat Selection page. The navigation bar shows the authenticated user's name and Logout option.

However,