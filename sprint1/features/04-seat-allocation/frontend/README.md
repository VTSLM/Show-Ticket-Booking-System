# Seat Selection — Frontend (React + Vite)

This is the interactive frontend for Sprint 1 Feature 04: Seat Selection & Allocation.

## Getting Started

```bash
# 1. Install dependencies
npm install

# 2. Run local development server
npm run dev
```

The frontend will run at `http://localhost:5173` and automatically proxy API calls to the FastAPI backend running on `http://localhost:8001`.

## Feature Implementation Overview
- **Phase 1: Fixture Data Integration**: Fetches initial seat layout matching the agreed schema contract.
- **Phase 2: Seat Map Grid**: Interactive 2D SVG/CSS grid grouped by section (VIP, Premium, General) and row, with BookMyShow-style cinema curve and color codes.
- **Phase 3: Compare-and-Swap Atomic Lock**: "Hold Seats" action triggers atomic CAS backend lock.
- **Phase 4: Real-time Countdown Timer**: Uses server-authoritative `expiresAt` timestamp to prevent client-side time drift.
- **Phase 5: Booking Confirmation**: Simulated payment workflow transitioning locked seats to booked with unique booking ID generation.
- **Phase 6: Live WebSocket Sync**: Instant push updates via `/ws/{show_id}` updating individual seats across all concurrent users.
- **Phase 7: Expired Hold UX**: Polite redirect and clear visual indicator if a seat hold expires before payment.
- **FR13: Booking Cancellation & Seat Recovery**: "My Bookings" page with one-click cancellation returning seats to the available pool.
