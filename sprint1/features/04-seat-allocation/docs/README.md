# Feature 04 — Seat Selection & Allocation

**Sprint 1 | Person 2 | Branch: `seat-allocation-khushi`**

---

## What this feature does

This feature implements the complete user-side seat booking flow — from browsing available seats to holding them, paying, and confirming the booking. It is designed to work **independently of other features** using fixture data in Phase 1, with a clear migration path to the shared database.

---

## Architecture Overview

```
┌─────────────────────────────────────────┐
│           React Frontend (Vite)         │
│   SeatMap → Sidebar → Payment → Done    │
│   WebSocket client for live updates     │
└─────────────────┬───────────────────────┘
                  │ HTTP / WebSocket
┌─────────────────▼───────────────────────┐
│         FastAPI Backend (Python)        │
│   /api/shows/{id}/seats  - seat list    │
│   /api/seats/lock        - atomic lock  │
│   /api/seats/release     - manual free  │
│   /api/seats/confirm     - book seats   │
│   /api/bookings/cancel   - refund flow  │
│   /ws/{show_id}          - real-time WS │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│     fixture_seats.py (Phase 1)          │
│     → Replace with DB calls in Phase 2  │
└─────────────────────────────────────────┘
```

---

## Phases Implemented

### Phase 1 — Fixture Data
- `fixture_seats.py` contains 30 handwritten seats across VIP / Premium / General sections
- Mix of `available`, `locked`, `booked`, `blocked` statuses
- **Migration**: Change the body of `get_all_seats()` to a DB SELECT — one line change

### Phase 2 — Seat Map Rendering
- Seats grouped by section → row for 2D grid
- Color-coded: green (available), purple (selected), amber (locked), grey (booked/blocked)
- Click to select/deselect; running price total in sidebar

### Phase 3 — Atomic Lock (the critical part)
- **How it works**: Single operation — check ALL seats are `available`, THEN write all locks. No intermediate state visible to other requests.
- **Race condition handled**: Two users hitting lock simultaneously: only one succeeds; the other gets 409 with the specific failed seat IDs
- **Compare-and-swap** pattern: check + write are indivisible
- **All-or-nothing**: if any seat fails, zero seats are locked

### Phase 4 — Hold Countdown & Auto-Expiry
- Frontend timer driven by server's `expires_at` — not a client-side duration (prevents tab-sleep drift)
- Background sweeper runs every 30 seconds, releases expired locks, broadcasts via WebSocket
- Manual release: user clicks "Release seats" → immediate `locked → available` transition

### Phase 5 — Confirm & Release
- Payment simulated (2s delay), then `confirm` API called
- Confirm re-verifies lock is still valid and belongs to current user
- `locked → booked` transition atomic at confirm step
- Cancellation (FR13): `booked → available` re-enters the seat pool

### Phase 6 — Real-Time Updates
- WebSocket per show (`/ws/{show_id}`)
- Server broadcasts only the changed seat ID + new status (not full layout)
- Frontend applies the update to just that one seat — no re-render of the full map
- Auto-reconnect with 3-second delay on disconnect

### Phase 7 — Failure UX
- Lock expired at checkout → `ExpiredScreen` with specific expired seat IDs shown
- Seats that were grabbed mid-selection → removed from selection + toast notification
- Payment fails mid-lock → user sees clear message, can retry without losing selection

---

## BookMyShow Design Decisions

| Scenario | BookMyShow approach | Our implementation |
|---|---|---|
| Race condition on lock | Optimistic lock with DB-level atomic update | `atomic_lock_seats()` — all-or-nothing write |
| Timer expiry | Server-side expiry + client countdown | `expires_at` from server; sweeper + countdown |
| Partial lock failure | Show which seats failed, keep rest selected | 409 with `failed_seat_ids`, UI removes them |
| Lock expired at payment | "Oops! Seats released" → back to selection | `ExpiredScreen` with retry button |
| Concurrent viewers | WebSocket push per seat change | Broadcast `SEAT_UPDATE` on every status change |
| Cancellation | Re-enters inventory | `cancel_booking()` transitions `booked → available` |

---

## File Structure

```
features/04-seat-selection/
├── backend/
│   ├── main.py              # FastAPI app — all endpoints + WS
│   ├── fixture_seats.py     # Phase 1 data + data-access helpers
│   ├── ws_manager.py        # WebSocket connection manager
│   ├── requirements.txt     # Python dependencies
│   └── run.py               # Dev runner
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main orchestrator (all 7 phases)
│   │   ├── api.js           # HTTP client
│   │   ├── index.css        # Design system
│   │   ├── main.jsx         # React entry
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js   # Phase 6 WS hook
│   │   │   ├── useCountdown.js   # Phase 4 timer hook
│   │   │   └── useToast.js       # Notification hook
│   │   └── components/
│   │       ├── SeatMap.jsx        # Phase 2 grid
│   │       ├── Sidebar.jsx        # Checkout panel + timer
│   │       ├── PaymentScreen.jsx  # Phase 5 payment
│   │       ├── ConfirmationScreen.jsx  # Phase 5 success
│   │       ├── ExpiredScreen.jsx  # Phase 7 UX
│   │       ├── BookingsPage.jsx   # Booking history + cancel
│   │       ├── Header.jsx         # Navigation
│   │       └── Toast.jsx          # Notifications
│   ├── vite.config.js
│   └── .env
└── docs/
    ├── README.md         ← this file
    ├── API.md            ← full API reference
    └── DESIGN.md         ← design decisions
```

---

## How to Run

### Backend
```bash
cd sprint1/features/04-seat-selection/backend
pip install -r requirements.txt
python run.py
# → http://localhost:8001
# → API docs: http://localhost:8001/docs
```

### Frontend
```bash
cd sprint1/features/04-seat-selection/frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Connecting to the Real Database (Phase 2+)

In `fixture_seats.py`, replace the function bodies:

```python
# Before (Phase 1):
def get_all_seats(show_id: str) -> list[dict]:
    return [deepcopy(s) for s in _seat_store.values()]

# After (Phase 2 — PostgreSQL/Supabase):
def get_all_seats(show_id: str) -> list[dict]:
    return db.query("SELECT * FROM show_seats WHERE show_id = %s", [show_id])
```

The atomic lock must use a DB transaction:
```sql
-- Phase 2 atomic lock:
BEGIN;
  SELECT * FROM show_seats 
  WHERE id = ANY($1) AND status = 'available'
  FOR UPDATE;          -- blocks other transactions
  
  UPDATE show_seats 
  SET status='locked', locked_by=$2, expires_at=$3
  WHERE id = ANY($1) AND status='available';
COMMIT;
```

---

## NFR Compliance

| NFR | Requirement | Implementation |
|---|---|---|
| Seat lock duration | Min 5 minutes | `LOCK_DURATION_MINUTES = 5` |
| No double booking | DB-level prevention | Atomic CAS lock; `all-or-none` policy |
| Auto-release | Expired locks released | Background sweeper every 30s |
| Real-time | New booking visible in <5s | WebSocket broadcast on every state change |
| Concurrent users | 500 concurrent | FastAPI async + WebSocket scales horizontally |
