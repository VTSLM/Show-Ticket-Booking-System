# Sprint 1 v2 — Offline Test Suite & QA Reports

This directory contains the automated test suites, testing configurations, scratch validation scripts, and comprehensive QA reports developed for `sprint1_v2`.

It is kept **untracked** in Git per `.gitignore` so that test code and artifacts do not clutter your feature commits.

---

## Directory Structure

```text
sprint1_v2_tests/
├── backend/
│   └── tests/
│       ├── conftest.py          # Schema-aware asyncpg mock (001_initial_schema & 002_payment_gateway)
│       ├── test_manager.py      # Manager Listing Pytest suite (12 tests)
│       ├── test_payments.py     # Payment Gateway Pytest suite (8 tests)
│       └── test_tickets.py      # Ticket Generation Pytest suite (9 tests)
│
├── frontend/
│   ├── playwright.config.ts     # Playwright configuration (Chrome channel, custom port support)
│   ├── test-results/            # Playwright execution artifacts and failure traces
│   └── tests/
│       ├── helpers/
│       │   └── mockAuth.ts      # Firebase Auth REST interceptor for deterministic UI tests
│       ├── manager/
│       │   ├── manager.spec.ts              # Manager UI & functional tests (7 tests)
│       │   ├── manager-edge.spec.ts         # Manager edge cases & validation (6 tests)
│       │   ├── manager-integration.spec.ts  # Manager real backend integration (2 tests)
│       │   └── manager_test.md              # Manager testing documentation & scenarios
│       ├── payment/
│       │   ├── payment.spec.ts              # Payment UI tests (4 tests)
│       │   ├── payment-edge.spec.ts         # Payment edge cases (6 tests)
│       │   ├── payment-integration.spec.ts  # Payment real backend integration (2 tests)
│       │   └── payment_test.md              # Payment testing documentation & scenarios
│       └── tickets/
│           ├── tickets.spec.ts              # Ticket generation UI tests (4 tests)
│           ├── tickets-edge.spec.ts         # Ticket generation edge cases (5 tests)
│           ├── tickets-integration.spec.ts  # Ticket real backend integration (2 tests)
│           └── tickets_test.md              # Ticket testing documentation & scenarios
│
├── reports/
│   ├── TEST_RESULTS_SIMPLE_SPRINT1_V2.md     # Executive plain-English test summary & scoreboard
│   ├── TESTING_DOCUMENTATION_SPRINT1_V2.md   # Complete QA test plan, scenarios & defect catalog
│   ├── manager_test.md                       # Manager Listing feature test report
│   ├── payment_test.md                       # Payment Gateway feature test report
│   └── tickets_test.md                       # Ticket Generation feature test report
│
├── scratch_scripts/
│   ├── check_db.py              # Supabase DB schema connection verification
│   ├── check_tables.py          # Table and column schema inspector
│   ├── test_show_creation_fix.py # Show creation & seat generation verification
│   ├── verify_three_modules.py  # End-to-end multi-module verification
│   └── verify_pdf_email.py      # ReportLab PDF & Gmail SMTP test runner
│
└── pytest.ini                   # Pytest configuration file
```

---

## How to Run Tests

### 1. Backend Pytest Suite
To run the backend tests against the `sprint1_v2` FastAPI codebase:

```powershell
# From project root:
$env:PYTHONPATH="d:\Sem 5\Se_project\sprint1_v2\backend"
python -m pytest "d:\Sem 5\Se_project\sprint1_v2_tests\backend\tests" -v
```

### 2. Frontend Playwright E2E Suite
To run the Playwright browser tests in Google Chrome:

```powershell
# In sprint1_v2/frontend directory:
cd "d:\Sem 5\Se_project\sprint1_v2\frontend"
npx playwright test --config="..\..\sprint1_v2_tests\frontend\playwright.config.ts"
```

