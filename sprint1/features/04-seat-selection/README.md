# Seat Selection

Sprint 1 scaffold — implementation is intentionally left open.

## Scope
- Display seat layout
- Select/deselect seats
- Show occupied vs available seats
- Calculate selected seats/amount

## Suggested work split
- `frontend/` — UI/pages/components for this feature
- `backend/` — FastAPI routes/services/models required by this feature
- `docs/` — API notes, flow diagrams, decisions, and test notes

## Completed Implementation
- [x] Decide frontend pages/components (SeatMap, Sidebar, Header, PaymentScreen, ConfirmationScreen, ExpiredScreen, BookingsPage)
- [x] Decide backend endpoints (`/api/shows/{id}/seats`, `/api/seats/lock`, `/api/seats/release`, `/api/seats/confirm`, `/api/bookings/cancel`, `/ws/{id}`)
- [x] Decide database fields/tables involved (documented in `docs/README.md` and `docs/API.md`)
- [x] Add validation and error states (atomic CAS concurrency, max 6 seats cap, 409 conflict handling, expired lock UX)
- [x] Add comprehensive test cases (`backend/test_seat_allocation.py` covering all 7 phases)
- [x] Document integration points with other features (detailed in `docs/README.md`)
