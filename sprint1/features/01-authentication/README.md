# User Authentication — Feature 01

Full implementation of the authentication feature for all stakeholders.

---

## Stack

| Layer    | Technology                            |
|----------|---------------------------------------|
| Frontend | Next.js 14 (App Router) + TailwindCSS |
| Backend  | FastAPI + asyncpg                     |
| Auth     | Firebase Authentication               |
| Database | PostgreSQL (Supabase) — shared schema |

---

## Folder structure

```
01-authentication/
├── backend/
│   ├── __init__.py
│   ├── config.py              # Pydantic-Settings env config
│   ├── database.py            # asyncpg pool management
│   ├── dependencies.py        # FastAPI deps: token verify, role guards
│   ├── firebase_admin_setup.py
│   ├── main.py                # FastAPI app entry-point
│   ├── requirements.txt
│   ├── router.py              # All /auth/* routes
│   ├── schemas.py             # Pydantic request/response models
│   └── service.py             # Business logic (register, verify, approvals)
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx          # Root layout + AuthProvider + Toaster
│   │   │   ├── globals.css
│   │   │   ├── page.tsx            # Root redirect based on role
│   │   │   ├── login/page.tsx      # Common login (email + Google)
│   │   │   ├── register/page.tsx   # Registration with role picker
│   │   │   ├── pending-approval/   # Waiting screen for managers/admins
│   │   │   ├── admin/dashboard/    # Admin dashboard + approval UI
│   │   │   ├── manager/dashboard/  # Manager dashboard (stub for Sprint 2)
│   │   │   └── browse/page.tsx     # Customer home (stub for Sprint 2)
│   │   ├── context/
│   │   │   └── AuthContext.tsx     # Global Firebase + profile state
│   │   └── lib/
│   │       ├── firebase.ts         # Firebase client SDK
│   │       └── api.ts              # Backend API client
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── .env.local.example
│
└── docs/
    └── TODO.md    # Design decisions, API contract, test cases
```

---

## Quick start

### Backend

```bash
cd sprint1/features/01-authentication/backend

# 1. Copy and fill env vars
cp ../../../.env.example .env
# Set DATABASE_URL and FIREBASE_SERVICE_ACCOUNT_PATH

# 2. Install deps
pip install -r requirements.txt

# 3. Run
uvicorn main:app --reload --port 8001
# Docs at http://localhost:8001/docs
```

### Frontend

```bash
cd sprint1/features/01-authentication/frontend

# 1. Copy and fill env vars
cp .env.local.example .env.local
# Set Firebase credentials + NEXT_PUBLIC_BACKEND_URL

# 2. Install deps
npm install

# 3. Run
npm run dev
# App at http://localhost:3000
```

---

## Authentication flow

```
Customer:  Register → Active immediately → Login → /browse
Manager:   Register → Pending approval  → Admin approves → Login → /manager/dashboard
Admin:     Register → Pending approval  → Admin approves → Login → /admin/dashboard
```

- All stakeholders share **one login page** (`/login`)
- Role-based redirect is determined by the backend `verify-token` response
- Managers and admins are stored with `status = inactive` until an admin approves them

## Admin approval

1. Manager/Admin registers → sees `/pending-approval` screen
2. Admin logs into `/admin/dashboard`
3. Admin sees the pending list and clicks **Approve** or **Reject**
   - Approve → `status = active`, user can now log in
   - Reject → user deleted from DB + Firebase account revoked

---

## API endpoints

| Method | Path                       | Auth            | Description                     |
|--------|----------------------------|-----------------|---------------------------------|
| POST   | `/auth/register`           | Public          | Register new user               |
| POST   | `/auth/verify-token`       | Public          | Verify Firebase token → profile |
| GET    | `/auth/me`                 | Bearer token    | Get own profile                 |
| GET    | `/auth/admin/pending`      | Admin only      | List pending approvals          |
| POST   | `/auth/admin/pending/{id}` | Admin only      | Approve / reject a user         |
| GET    | `/health`                  | Public          | Health check                    |
