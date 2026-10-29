# Feature 04 — Seat Allocation

Combined customer-side seat selection and manager-side seat layout/pricing feature.

## Folders

- `backend/` — FastAPI app with customer seat-selection routes and manager layout routes.
- `frontend/` — Next.js app with customer seat-selection and manager layout pages.
- `database/` — SQL schema/migrations for both original data models.
- `docs/` — API notes, setup, and integration caveats.

Start with `docs/INTEGRATION.md` and `database/README.md`.

**Known limitation:** the two source branches use separate tables for reusable manager layouts and show-specific customer seats. They are exposed through one application, but no layout-publish/sync operation was present in the supplied code. That needs implementation and tests before manager-edited layouts automatically appear to customers.
