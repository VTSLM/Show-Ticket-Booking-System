# Login Testing Documentation

## 1. Overview

This document describes the automated testing performed for the **Login and Authentication** module of the Show Ticket Booking System.

The Login module is responsible for:

- User login using email and password
- Firebase authentication
- Backend token verification
- User registration status verification
- Role-based authorization
- Session persistence
- Handling authentication failures
- Preventing repeated login submissions
- Handling inactive and blocked accounts

The testing is implemented using **Playwright** and is organized into four test files.

### Test Files

```text
frontend/
└── tests/
    └── login/
        ├── login.spec.ts
        ├── authorization.spec.ts
        ├── login-edge.spec.ts
        └── firebase-auth.spec.ts
```

---

# 2. Login Testing Scope

The Login testing scope is divided into four major areas:

| Area | Purpose |
|---|---|
| Login UI & Functional Testing | Verify login page controls, input validation and normal login behaviour |
| Authentication & Authorization | Verify access based on authentication status and user role |
| Edge Case Testing | Verify abnormal authentication conditions and session behaviour |
| Firebase Integration Testing | Verify the complete Firebase → Backend → Supabase authentication flow |

---

# 3. Test Scenarios

Before automating the tests, the following scenarios were identified from the Login module requirements and implementation.

## 3.1 Login UI and Functional Scenarios

| ID | Test Scenario | Expected Result |
|---|---|---|
| LOGIN-UI-01 | Open the login page | Required login controls are displayed |
| LOGIN-UI-02 | Submit the login form with empty required fields | Browser validation prevents submission |
| LOGIN-UI-03 | Enter an invalid email address | Invalid email format is rejected |
| LOGIN-UI-04 | Enter a password | Password is masked |
| LOGIN-01 | Login with valid credentials | User is authenticated and redirected to `/browse` |
| LOGIN-02 | Login with an incorrect password | Authentication fails and user is not redirected to `/browse` |

---

## 3.2 Authentication and Authorization Scenarios

The application supports different user roles, including:

- Customer
- Manager
- Admin

The following scenarios verify whether users can access resources according to their authentication status and role.

| ID | Test Scenario | Expected Result |
|---|---|---|
| LOGIN-AUTH-01 | Unauthenticated user accesses `/bookings` | User is redirected to login |
| LOGIN-AUTH-02 | Active customer accesses `/bookings` | Access is allowed |
| LOGIN-AUTH-03 | Customer accesses `/manager` | Access is denied |
| LOGIN-AUTH-04 | Customer accesses `/admin` | Access is denied |
| LOGIN-AUTH-05 | Active manager accesses `/manager` | Access is allowed |
| LOGIN-AUTH-06 | Manager accesses `/admin` | Access is denied |
| LOGIN-AUTH-07 | Active admin accesses `/admin` | Access is allowed |

---

## 3.3 Login Edge-Case Scenarios

Normal login behaviour is not sufficient for authentication testing. The following edge cases verify the behaviour of the application when authentication or token verification does not behave normally.

| ID | Test Scenario | Expected Result |
|---|---|---|
| LOGIN-EDGE-01 | Authenticate successfully and refresh the page | Authenticated session remains available |
| LOGIN-EDGE-02 | Firebase authentication succeeds but backend token verification fails | User is not redirected to `/browse` |
| LOGIN-EDGE-03 | Authentication fails | Login button returns to its normal state |
| LOGIN-EDGE-04 | Click the login button repeatedly while authentication is in progress | Multiple submissions are prevented |

These tests are particularly important because authentication involves multiple asynchronous operations:

```text
Login Form
    ↓
Firebase Authentication
    ↓
Firebase ID Token
    ↓
Backend Token Verification
    ↓
User Profile / Role
    ↓
Application Access
```

A failure at any stage should be handled without leaving the application in an inconsistent state.

---

# 4. Firebase Integration Scenarios

The application uses Firebase Authentication together with the application's backend and Supabase database.

Therefore, authentication testing must verify more than whether Firebase accepts the credentials.

The following integration scenarios verify the relationship between Firebase authentication and the application's user records.

| ID | Test Scenario | Expected Result |
|---|---|---|
| FIREBASE-01 | Firebase user exists but corresponding Supabase user does not exist | Login is rejected |
| FIREBASE-02 | Firebase user exists and Supabase account has `inactive` status | Login is rejected with account-pending message |
| FIREBASE-03 | Firebase user exists and Supabase account has `blocked` status | Login is rejected with account-blocked message |

The authentication flow being tested is:

```text
                    ┌──────────────────┐
                    │  Login Page      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Firebase Auth    │
                    └────────┬─────────┘
                             │
                       Firebase ID Token
                             │
                             ▼
                    ┌──────────────────┐
                    │ Backend API       │
                    │ /auth/verify-token│
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Supabase / DB     │
                    │ User + Role +     │
                    │ Status            │
                    └────────┬─────────┘
                             │
                    ┌────────┴─────────┐
                    ▼                  ▼
                 Allowed            Rejected
                    │                  │
                    ▼                  ▼
                /browse        Error / Login remains
```

---

# 5. What Should Be Automated?

Automation is appropriate for login testing because authentication contains many repeatable, deterministic scenarios.

## 5.1 Scenarios Suitable for Automation

The following are automated:

### UI Validation

- Login page rendering
- Required-field validation
- Email format validation
- Password masking
- Login button behaviour

### Functional Authentication

- Successful login
- Invalid password
- Authentication failure handling
- Session persistence

### Authorization

- Unauthenticated access
- Customer permissions
- Manager permissions
- Admin permissions

### Edge Cases

- Backend token verification failure
- Authentication failure recovery
- Repeated login submission
- Page refresh after authentication

### Firebase Integration

- Firebase-only account
- Inactive manager
- Blocked user

These scenarios are suitable for automation because they have clearly defined inputs and expected outcomes and can be repeatedly executed without manual interaction.

---

# 6. Scenarios Not Currently Automated

Some scenarios are not included in the current automated suite.

## Google Authentication

The Login page provides a **Continue with Google** option.

However, Google OAuth involves an external authentication provider and browser interaction outside the application's own login page. It is therefore not included in the current automated Playwright suite.

This can be tested separately using an appropriate controlled authentication strategy if required.

# 7. Test Automation Tools

## Playwright

**Playwright** is used for frontend and end-to-end browser automation.

It provides:

- Browser automation
- Element interaction
- Assertions
- Authentication testing
- Network interception
- Page navigation testing
- Screenshot capture on failure
- Trace collection
- Headed and headless execution

The project uses:

```text
@playwright/test
```

---

## Testing Architecture

The Login tests operate primarily through the browser:

```text
Playwright
    │
    ▼
Next.js Frontend
    │
    ├── Firebase Authentication
    │
    ▼
Backend API
    │
    ▼
Supabase Database
```

This allows the Firebase integration tests to verify the actual authentication flow rather than testing only mocked responses.

---

# 8. Test File Organization

## `login.spec.ts`

Contains the basic Login page and functional login tests.

Tests covered:

```text
LOGIN-UI-01
LOGIN-UI-02
LOGIN-UI-03
LOGIN-UI-04
LOGIN-UI-05
LOGIN-01
LOGIN-02
```

Total:

```text
7 tests
```

---

## `authorization.spec.ts`

Contains authentication and role-based authorization tests.

Tests covered:

```text
LOGIN-AUTH-01
LOGIN-AUTH-02
LOGIN-AUTH-03
LOGIN-AUTH-04
LOGIN-AUTH-05
LOGIN-AUTH-06
LOGIN-AUTH-07
```

Total:

```text
7 tests
```

---

## `login-edge.spec.ts`

Contains edge cases related to authentication failures, session persistence and repeated submissions.

Tests covered:

```text
LOGIN-EDGE-01
LOGIN-EDGE-02
LOGIN-EDGE-03
LOGIN-EDGE-04
```

Total:

```text
4 tests
```

These tests require the following environment variables:

```text
TEST_LOGIN_EMAIL
TEST_LOGIN_PASSWORD
```

---

## `firebase-auth.spec.ts`

Contains Firebase and backend integration tests.

Tests covered:

```text
FIREBASE-01
FIREBASE-02
FIREBASE-03
```

Total:

```text
3 tests
```

These tests require dedicated Firebase/Supabase test accounts.

---

# 9. Test Data Requirements

The automated tests should use dedicated test accounts rather than personal accounts.

For the normal Login and edge-case tests:

```text
TEST_LOGIN_EMAIL
TEST_LOGIN_PASSWORD
```

For Firebase integration tests:

```text
TEST_FIREBASE_ONLY_EMAIL
TEST_FIREBASE_ONLY_PASSWORD

TEST_INACTIVE_MANAGER_EMAIL
TEST_INACTIVE_MANAGER_PASSWORD

TEST_BLOCKED_EMAIL
TEST_BLOCKED_PASSWORD
```

### Firebase-only User

The Firebase-only test account must:

- Exist in Firebase Authentication
- Not have a corresponding user record in Supabase

Expected result:

```text
Authentication rejected
```

### Inactive Manager

The inactive manager account must:

- Exist in Firebase
- Have a corresponding Supabase user
- Have manager role
- Have `status = inactive`

Expected result:

```text
Account pending admin approval
```

### Blocked User

The blocked account must:

- Exist in Firebase
- Have a corresponding Supabase user
- Have `status = blocked`

Expected result:

```text
Account blocked
```

---

# 10. Environment Configuration

Test credentials should **not** be hard-coded into the test files.

They should be supplied through environment variables.

For example:

```bash
export TEST_LOGIN_EMAIL="test@example.com"
export TEST_LOGIN_PASSWORD="test-password"
```

Firebase integration variables:

```bash
export TEST_FIREBASE_ONLY_EMAIL="firebase-only@example.com"
export TEST_FIREBASE_ONLY_PASSWORD="password"

export TEST_INACTIVE_MANAGER_EMAIL="inactive-manager@example.com"
export TEST_INACTIVE_MANAGER_PASSWORD="password"

export TEST_BLOCKED_EMAIL="blocked-user@example.com"
export TEST_BLOCKED_PASSWORD="password"
```

These credentials must not be committed to Git.

---

# 11. How to Run the Tests

## Step 1: Start the Backend

From the backend directory, start the FastAPI server:

```bash
uvicorn main:app --reload --port 8000
```

The backend should be available at:

```text
http://localhost:8000
```

---

## Step 2: Start the Frontend

From the frontend directory:

```bash
npm run dev
```

The frontend should be available at:

```text
http://localhost:3000
```

---

## Step 3: Set Test Credentials

Before running the tests that require a real test account:

```bash
export TEST_LOGIN_EMAIL="your-test-email"
export TEST_LOGIN_PASSWORD="your-test-password"
```

Set the Firebase integration credentials as required by `firebase-auth.spec.ts`.

---

## Step 4: Run All Login Tests

From:

```text
frontend/
```

run:

```bash
npx playwright test tests/login/
```

---

## Step 5: Run Tests in Headed Mode

To see the browser while the tests execute:

```bash
npx playwright test tests/login/ --headed
```

This is useful during test development and debugging.

---

## Step 6: Run an Individual Test File

### Login UI and functional tests

```bash
npx playwright test tests/login/login.spec.ts
```

### Authorization tests

```bash
npx playwright test tests/login/authorization.spec.ts
```

### Edge-case tests

```bash
npx playwright test tests/login/login-edge.spec.ts
```

### Firebase integration tests

```bash
npx playwright test tests/login/firebase-auth.spec.ts
```

---

# 12. Test Execution Results

The complete Login test suite currently contains:

| Test File | Number of Tests |
|---|---:|
| `login.spec.ts` | 7 |
| `authorization.spec.ts` | 7 |
| `login-edge.spec.ts` | 4 |
| `firebase-auth.spec.ts` | 3 |
| **Total** | **21** |

A test marked as **skipped** because required test credentials are unavailable should not be interpreted as a functional failure.

Similarly, a test that fails during test setup because an environment variable is missing is a **test-environment/configuration issue**, not necessarily an application defect.

---

# 13. Test Results and Reporting

Playwright automatically reports:

- Passed tests
- Failed tests
- Skipped tests
- Execution time
- Error messages
- Screenshots for failures
- Traces for debugging

The project configuration retains traces for failed tests and screenshots when failures occur.

For example, a failed trace can be opened using:

```bash
npx playwright show-trace <path-to-trace.zip>
```

---

# 14. Recommended Testing Workflow

The Login testing process should follow this order:

```text
1. Identify Login Requirements
           ↓
2. Create Test Scenarios
           ↓
3. Classify Scenarios
   ├── Functional
   ├── Authorization
   ├── Edge Cases
   └── Integration
           ↓
4. Identify Automatable Scenarios
           ↓
5. Prepare Controlled Test Accounts
           ↓
6. Implement Playwright Tests
           ↓
7. Execute Tests
           ↓
8. Analyse Failures
           ↓
9. Fix Application/Test Issues
           ↓
10. Re-run Regression Suite
           ↓
11. Document Results
```

---

# 15. Summary

The Login testing implementation provides coverage across the complete authentication lifecycle:

```text
Login UI
   ↓
Input Validation
   ↓
Firebase Authentication
   ↓
ID Token Verification
   ↓
Backend Authentication
   ↓
Supabase User Validation
   ↓
Role & Status Verification
   ↓
Authorization
   ↓
Application Access
```

The four Playwright test files provide **21 automated test cases** covering:

- Login UI validation
- Successful and failed login
- Authentication
- Role-based authorization
- Session persistence
- Authentication edge cases
- Firebase integration
- Inactive accounts
- Blocked accounts
- Authentication failure recovery

This provides a reusable automated regression suite for the Login module and can be executed whenever changes are made to the authentication, authorization, Firebase, backend, or Login UI components.