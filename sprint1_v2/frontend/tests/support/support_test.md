# Support Queries Testing

## 1. Overview

This document describes the testing performed for the **Support Queries** feature of the Show Ticket Booking System.

The Support Queries feature allows customers to:

- View their support requests
- Create a new support request
- Select a support category
- Associate a request with a booking
- View individual support requests
- Reply to open support requests
- Reopen resolved requests
- Filter requests by status
- Prevent replies to closed requests

The feature was tested using **Playwright** for frontend UI, edge-case, and integration testing.

---

## 2. Testing Objectives

The main objectives of testing were:

1. Verify that authenticated customers can access Support Queries.
2. Verify that unauthenticated users are redirected appropriately.
3. Verify that customers can create support requests.
4. Verify that all support categories are available.
5. Verify booking selection and booking-related validation.
6. Verify subject and message validation.
7. Verify that customers can view submitted support requests.
8. Verify that customers can send replies.
9. Verify that resolved requests can be reopened.
10. Verify that closed requests cannot receive replies.
11. Verify filtering of support requests by status.
12. Verify complete customer workflows through integration tests.
13. Identify application issues through automated testing rather than modifying application code to make tests pass.

---

## 3. Feature Under Test

The Support Queries feature contains the following customer-facing routes:

```text
/support
/support/new
/support/[id]
```

### `/support`

Displays the customer's support requests.

The page allows the customer to:

- View existing requests
- Filter requests by status
- Navigate to a specific request
- Create a new support request

### `/support/new`

Allows the customer to create a support request.

The form contains:

- Category
- Booking
- Subject
- Problem description
- Submit button

### `/support/[id]`

Displays an individual support request.

The page allows customers to:

- View request details
- View previous messages
- Send replies
- Reopen resolved requests
- View closed-request restrictions

---

## 4. Support Request Categories

The following categories were tested:

| Category | Value |
|---|---|
| Payment issue | `payment` |
| Booking issue | `booking` |
| Refund request | `refund` |
| Account / login | `account` |
| Something else | `other` |

---

## 5. Form Validation

The following validation rules are implemented and tested.

### Booking Validation

For categories that require a booking, the customer must select a booking.

Expected validation message:

```text
Please select the booking this is about.
```

### Subject Validation

The subject must contain at least 5 characters.

Expected validation message:

```text
Subject must be at least 5 characters.
```

### Message Validation

The problem description must contain at least 10 characters.

Expected validation message:

```text
Please describe the problem in at least 10 characters.
```

---

## 6. Test Scenarios

### 6.1 Basic UI Test Scenarios

| Test ID | Test Scenario |
|---|---|
| SUPPORT-UI-01 | Support request list loads successfully |
| SUPPORT-UI-02 | Customer can navigate to New Request |
| SUPPORT-UI-03 | All support request categories are available |
| SUPPORT-UI-04 | Booking is required for Booking category |
| SUPPORT-UI-05 | Booking is required for Refund category |
| SUPPORT-UI-06 | Booking is optional for Account/Login category |
| SUPPORT-UI-07 | Subject validation works correctly |
| SUPPORT-UI-08 | Message validation works correctly |
| SUPPORT-UI-09 | Customer can select a booking |
| SUPPORT-UI-10 | Customer can submit a support request |
| SUPPORT-UI-11 | Customer can view request details |
| SUPPORT-UI-12 | Customer can send a reply |
| SUPPORT-UI-13 | Resolved request provides Reopen option |
| SUPPORT-UI-14 | Closed request does not provide reply form |
| SUPPORT-UI-15 | Customer can filter requests by status |

The basic UI tests verify that the individual Support Queries interface elements and workflows work correctly from the customer's perspective.

### 6.2 Edge Case Test Scenarios

| Test ID | Test Scenario |
|---|---|
| SUPPORT-EDGE-01 | Unauthenticated user is redirected from Support page |
| SUPPORT-EDGE-02 | Unauthenticated user is redirected from New Request page |
| SUPPORT-EDGE-03 | Invalid/non-existent support request is handled |
| SUPPORT-EDGE-04 | Subject below minimum length is rejected |
| SUPPORT-EDGE-05 | Message below minimum length is rejected |
| SUPPORT-EDGE-06 | Empty message cannot be submitted |
| SUPPORT-EDGE-07 | Resolved request can be reopened with a message |
| SUPPORT-EDGE-08 | Closed request cannot be replied to |

These tests focus on invalid input, authentication restrictions, boundary conditions, and request-status restrictions.

### 6.3 Integration Test Scenarios

| Test ID | Test Scenario |
|---|---|
| SUPPORT-INT-01 | Customer can create a support request |
| SUPPORT-INT-02 | Customer can view a request and send a reply |
| SUPPORT-INT-03 | Customer can reopen a resolved request |
| SUPPORT-INT-04 | Customer can filter support requests by status |
| SUPPORT-INT-05 | Closed request does not allow customer reply |

These tests verify complete customer workflows involving multiple UI actions and API interactions.

---

## 7. Automated Testing

The Support Queries feature was tested using **Playwright**.

The automated test suite is divided into three groups:

```text
Basic UI Tests
       ↓
Edge Case Tests
       ↓
Integration Tests
```

This separation makes it easier to identify whether a failure is related to a basic UI interaction, an invalid/boundary condition, or a complete workflow.

### 7.1 Basic UI Testing

The basic UI suite verifies individual Support Queries features and controls.

It covers:

- Support page loading
- New Request navigation
- Category selection
- Booking requirements
- Booking selection
- Subject validation
- Message validation
- Request submission
- Request details
- Customer replies
- Resolved requests
- Closed requests
- Status filtering

### 7.2 Edge Case Testing

The edge-case suite verifies behavior under invalid or restricted conditions.

It covers:

- Unauthenticated access
- Invalid request IDs
- Short subjects
- Short messages
- Empty messages
- Reopening resolved requests
- Reply restrictions for closed requests

### 7.3 Integration Testing

The integration suite verifies complete workflows.

Examples include:

```text
Login
  ↓
Support
  ↓
New Request
  ↓
Select Category
  ↓
Select Booking
  ↓
Enter Subject
  ↓
Enter Message
  ↓
Submit Request
  ↓
Request Details
```

Another integration workflow:

```text
Resolved Request
       ↓
Reopen Request
       ↓
Enter Message
       ↓
Submit
       ↓
Request Reopened
```

---

## 8. Testing Tools

The following tools were used:

### Playwright

Playwright was used for frontend browser automation and end-to-end testing.

### TypeScript

The Playwright tests were written in TypeScript.

### FastAPI

The backend API was used as part of the application's Support Queries workflow.

### Pytest

Pytest was used for backend Support Queries API testing.

### PostgreSQL / Supabase

The Support Queries backend uses the project's database layer for support request data.

---

## 9. Test Environment Setup

Before running the Support Queries tests, both the backend and frontend should be running.

### 9.1 Start Backend

Activate the project's Python virtual environment:

```bash
source venv/bin/activate
```

Then start FastAPI:

```bash
uvicorn main:app --reload --port 8000
```

The backend should be available at:

```text
http://localhost:8000
```

### 9.2 Start Frontend

Open another terminal and navigate to the frontend:

```bash
cd frontend
```

Start Next.js:

```bash
npm run dev
```

The frontend should be available at:

```text
http://localhost:3000
```

### 9.3 Set Test Credentials

The authenticated Playwright tests require test credentials.

Set them in the terminal before running the tests:

```bash
export TEST_LOGIN_EMAIL="your-test-user-email"
export TEST_LOGIN_PASSWORD="your-test-user-password"
```

These credentials should belong to a valid test customer account.

Do not commit these credentials to Git.

---

## 10. Test Files

The Support Queries Playwright tests are organized as follows:

```text
frontend/
└── tests/
    └── support/
        ├── support.spec.ts
        ├── support-edge.spec.ts
        └── support-integration.spec.ts
```

### `support.spec.ts`

Contains the basic UI tests.

### `support-edge.spec.ts`

Contains edge-case and negative tests.

### `support-integration.spec.ts`

Contains end-to-end integration workflows.

---

## 11. Backend Support Tests

Backend Support Queries testing was also performed using Pytest.

The relevant backend test files are:

```text
backend/tests/
├── test_support.py
└── test_support_admin.py
```

The backend tests cover Support Queries API behavior for customers and administrators.

The administrator tests initially exposed a test-data mismatch where mocked `created_at` values were strings while the application expected Python `datetime` objects and called `.isoformat()`.

The test mocks were corrected to use Python `datetime` values, matching the behavior of PostgreSQL `timestamptz` data.

After this correction, the administrator Support Queries backend tests passed.

---

## 12. Running the Tests

Navigate to the frontend directory:

```bash
cd frontend
```

### 12.1 Run All Support Tests

```bash
npx playwright test tests/support/ --headed
```

This runs:

```text
support.spec.ts
support-edge.spec.ts
support-integration.spec.ts
```

### 12.2 Run Basic UI Tests

```bash
npx playwright test tests/support/support.spec.ts --headed
```

### 12.3 Run Edge Case Tests

```bash
npx playwright test tests/support/support-edge.spec.ts --headed
```

### 12.4 Run Integration Tests

```bash
npx playwright test tests/support/support-integration.spec.ts --headed
```

### 12.5 Run a Specific Test

For example:

```bash
npx playwright test tests/support/support-integration.spec.ts -g "SUPPORT-INT-04" --headed
```

### 12.6 Run Without Headed Mode

```bash
npx playwright test tests/support/
```

---

## 13. Test Results

### Basic UI Tests

```text
15 passed
0 failed
```

Result:

```text
SUPPORT-UI: 15/15 PASSED
```

### Edge Case Tests

```text
8 passed
0 failed
```

Result:

```text
SUPPORT-EDGE: 8/8 PASSED
```

### Integration Tests

```text
5 passed
0 failed
```

Result:

```text
SUPPORT-INT: 5/5 PASSED
```

---

## 14. Overall Test Summary

| Test Suite | Total | Passed | Failed |
|---|---:|---:|---:|
| Basic UI | 15 | 15 | 0 |
| Edge Cases | 8 | 8 | 0 |
| Integration | 5 | 5 | 0 |
| **Total** | **28** | **28** | **0** |

### Overall Result

```text
28 / 28 PASSED
0 FAILED
```

Therefore:

**Support Queries automated testing: 28/28 tests passed successfully.**

---

## 15. Issues Encountered During Test Development

Several issues were identified and resolved while developing the automated tests.

These were primarily issues with test implementation, locators, and test data rather than failures in the Support Queries application itself.

### 15.1 Password Locator Conflict

The login page contains both:

- Password input
- Show/Hide Password button

A generic label-based locator matched both elements.

The test initially used a generic password label locator, which caused Playwright strict-mode problems.

The locator was changed to:

```ts
page.locator("#password")
```

This uniquely identifies the password input.

### 15.2 Incorrect Message Locator on New Request Page

The New Support Request page uses:

```html
<textarea id="message">
```

with the label:

```text
Describe the problem
```

The test initially attempted to locate the field using:

```text
Your message
```

However, `"Your message"` is used on the request detail/reply page.

The New Request tests were corrected to use:

```ts
page.locator("#message")
```

### 15.3 Incorrect Booking API Mock

The New Support Request page retrieves bookings through:

```text
GET /api/bookings
```

The integration test initially mocked:

```text
/api/support/bookings
```

which is not the endpoint used by the actual frontend.

The test was corrected to mock:

```text
/api/bookings
```

This allowed the booking selection workflow to execute correctly.

### 15.4 Duplicate Subjects in Filtering Test

The initial filtering integration test used the same subject for multiple request statuses.

For example:

```text
Open      → Booking problem
Resolved  → Booking problem
Closed    → Booking problem
```

Playwright therefore found multiple elements when the test expected one.

The test data was changed to unique subjects:

```text
Open      → Open booking problem
Resolved  → Resolved payment issue
Closed    → Closed account issue
```

The filtering test then verified:

```text
Before filtering:

✓ Open booking problem
✓ Resolved payment issue
✓ Closed account issue


After selecting Resolved:

✓ Resolved payment issue

✗ Open booking problem
✗ Closed account issue
```

This makes the test verify the actual filtering behavior.

### 15.5 Closed Request Text Locator

The closed request page contains additional text around the closed-request message.

The test initially used:

```ts
page.getByText("This request is closed", {
  exact: true
})
```

The actual UI contains additional text, so the exact locator was too restrictive.

The test was changed to:

```ts
page.getByText(/This request is closed/)
```

This correctly identifies the closed-request message.

---

## 16. Testing Approach

The Support Queries feature was tested at three levels.

### Level 1: Basic UI Testing

The basic UI tests verify individual user interface behaviors.

Example workflow:

```text
Open Support
    ↓
Open New Request
    ↓
Select Category
    ↓
Select Booking
    ↓
Enter Subject
    ↓
Enter Message
    ↓
Submit Request
```

### Level 2: Edge Case Testing

Edge tests verify invalid and restricted scenarios.

Example:

```text
Unauthenticated User
        ↓
      /support
        ↓
   Redirect to Login
```

Another example:

```text
Subject < 5 characters
        ↓
    Validation Error
        ↓
Request not submitted
```

Another example:

```text
Closed Request
        ↓
Reply Form unavailable
```

### Level 3: Integration Testing

Integration tests verify complete workflows across multiple application interactions.

Example:

```text
Login
  ↓
Support
  ↓
New Request
  ↓
Select Category
  ↓
Select Booking
  ↓
Enter Request Details
  ↓
Submit
  ↓
Request Created
  ↓
Request Details Page
```

Another workflow:

```text
Resolved Request
       ↓
Reopen Request
       ↓
Enter Message
       ↓
Submit
       ↓
Request Reopened
```

---

## 17. Test Automation Principles

The following principles were followed while creating the tests.

### 17.1 Test the Existing Application

Application code was not modified simply to make a test pass.

If a test exposes an actual application defect, it should be documented as a defect rather than hiding the problem by changing application behavior.

### 17.2 Use Stable Locators

Where possible, tests use:

- IDs
- Accessible labels
- Roles
- Visible text
- Stable semantic selectors

Examples:

```ts
page.locator("#password")
page.locator("#message")
page.getByRole("button", { name: /send/i })
page.getByRole("heading", { name: "Contact Support" })
```

### 17.3 Avoid Ambiguous Assertions

When multiple elements contain the same text, the test data is made unique or a more specific locator is used.

### 17.4 Separate Test Types

Tests are separated into:

```text
Basic UI
Edge Cases
Integration
```

This makes failures easier to identify and maintain.

### 17.5 Use Controlled API Responses

Integration tests use mocked API responses where predictable data is required.

This prevents tests from depending unnecessarily on changing database contents.

---

## 18. Support Queries API Coverage

The customer Support Queries workflow uses the following API operations:

| Operation | Endpoint | Purpose |
|---|---|---|
| GET | `/api/support/requests` | List customer support requests |
| GET | `/api/support/requests/{id}` | Get a specific request |
| POST | `/api/support/requests` | Create a support request |
| POST | `/api/support/requests/{id}/messages` | Send a reply |
| POST | `/api/support/requests/{id}/reopen` | Reopen a resolved request |
| GET | `/api/bookings` | Retrieve customer bookings |

The tests verify the frontend behavior associated with these operations.

---

## 19. Test Execution Workflow

The recommended workflow for running Support Queries testing is:

### Step 1: Activate the Python environment

```bash
source venv/bin/activate
```

### Step 2: Start the backend

```bash
uvicorn main:app --reload --port 8000
```

### Step 3: Start the frontend

In another terminal:

```bash
cd frontend
npm run dev
```

### Step 4: Set test credentials

```bash
export TEST_LOGIN_EMAIL="your-test-user-email"
export TEST_LOGIN_PASSWORD="your-test-user-password"
```

### Step 5: Run the basic UI tests

```bash
npx playwright test tests/support/support.spec.ts --headed
```

### Step 6: Run the edge-case tests

```bash
npx playwright test tests/support/support-edge.spec.ts --headed
```

### Step 7: Run the integration tests

```bash
npx playwright test tests/support/support-integration.spec.ts --headed
```

### Step 8: Run the complete Support Queries suite

```bash
npx playwright test tests/support/ --headed
```

---

## 20. Expected Final Output

A successful complete test run should report:

```text
Running 28 tests

28 passed
0 failed
```

The individual suites should report:

```text
Basic UI Tests:
15 passed

Edge Case Tests:
8 passed

Integration Tests:
5 passed
```

---

## 21. Final Testing Status

The Support Queries feature has been tested using:

- Basic UI testing
- Functional testing
- Form validation testing
- Authentication testing
- Negative testing
- Edge-case testing
- Integration testing
- API request mocking
- Status filtering testing
- Request creation testing
- Reply testing
- Request reopening testing
- Closed-request restriction testing

Final automated result:

```text
========================================
SUPPORT QUERIES TESTING
========================================

Basic UI Tests       : 15/15 PASSED
Edge Case Tests      :  8/8  PASSED
Integration Tests    :  5/5  PASSED
----------------------------------------
TOTAL                : 28/28 PASSED
FAILED               : 0
========================================
```

**Status: PASS — Support Queries automated testing is complete with 28/28 tests passing.**

---

## 22. Conclusion

The Support Queries feature was tested comprehensively using Playwright.

The automated test suite covers the major customer workflows as well as:

- Authentication restrictions
- Support request creation
- Support categories
- Booking selection
- Form validation
- Request details
- Customer replies
- Resolved request reopening
- Closed request restrictions
- Status filtering
- Invalid request handling
- Boundary conditions
- Integration workflows

All **28 automated Support Queries tests passed successfully**.

### Final Result

```text
Support Queries Testing
-----------------------

Basic UI Tests       : 15/15 PASSED
Edge Case Tests      :  8/8  PASSED
Integration Tests    :  5/5  PASSED

Total                : 28/28 PASSED
Failed               : 0
```

**Status: PASS**
