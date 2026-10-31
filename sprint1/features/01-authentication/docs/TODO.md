# Notes / Decisions

## User flow

```
Register page
  ├── User picks role (Customer | Manager | Admin)
  ├── Fills name / email / phone / password  (or Google OAuth)
  ├── Firebase account is created client-side
  └── POST /auth/register  →  backend upserts user + role in DB
        ├── Customer  → status = active  → redirect /login
        └── Manager / Admin → status = inactive → redirect /pending-approval

Login page
  ├── email+password  or  Google OAuth  →  Firebase token
  └── POST /auth/verify-token  →  backend returns profile + redirect_to
        ├── active   → redirect_to from profile (role-specific dashboard)
        └── inactive → redirect /pending-approval

Admin dashboard  (admin only)
  ├── GET  /auth/admin/pending          → list inactive registrations
  └── POST /auth/admin/pending/{id}     → approve (set active) | reject (delete)
```

## Stakeholder roles & redirects

| Role     | Registration | Redirect after login     |
|----------|-------------|--------------------------|
| customer | instant     | `/browse`                |
| manager  | admin approval required | `/manager/dashboard` |
| admin    | admin approval required | `/admin/dashboard`   |

## API contract

| Method | Path                       | Auth            | Description                        |
|--------|----------------------------|-----------------|------------------------------------|
| POST   | `/auth/register`           | None (public)   | Register new user                  |
| POST   | `/auth/verify-token`       | None (public)   | Verify Firebase token → profile    |
| GET    | `/auth/me`                 | Bearer token    | Get current user profile           |
| GET    | `/auth/admin/pending`      | Admin only      | List pending approvals             |
| POST   | `/auth/admin/pending/{id}` | Admin only      | Approve or reject a pending user   |
| GET    | `/health`                  | None            | Health check                       |

## Database dependency

- `users` — stores firebase_uid, name, email, phone, status
- `roles` — code values: `customer`, `manager`, `admin`
- `user_roles` — many-to-many join

Non-customer roles are stored with `status = 'inactive'` until admin sets them to `active`.

## Dependencies on other features

- **Feature 02 (Manager Show Listing)** — manager dashboard stub is here, full content lands in Feature 02.
- **Feature 03 (Browse Nearby Shows)** — `/browse` page stub is here.
- **Shared DB** — uses the `users`, `roles`, `user_roles` tables from `001_initial_schema.sql`.

## Test cases

- [x] Customer registers → status active → can log in immediately
- [x] Manager registers → status inactive → sees pending-approval page
- [ ] Admin approves manager → manager can now log in
- [ ] Admin rejects user → user removed, Firebase account deleted
- [x] Wrong password → clear error message, no account lockout (Firebase handles)
- [ ] Google login with unregistered account → redirect to /register
- [ ] Inactive user tries to log in → blocked, sees pending-approval page
- [ ] Non-admin hits /auth/admin/pending → 403 Forbidden
