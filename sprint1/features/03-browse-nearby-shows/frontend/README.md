# Cinema frontend (React + Vite)
```bash
npm install
cp .env.example .env     # VITE_API_URL=http://localhost:8000/api/v1
npm run dev              # http://localhost:3000  (matches backend CORS_ORIGINS)
```
Backend: `uvicorn app.main:app --reload` (+ `python -m scripts.seed` for demo data).

**Live from backend:** city picker, movie list (grouped per event), search, genre filter, show details, showtimes by venue/date, seat-category pricing + availability.
**Mocked until backend gets endpoints:** per-seat map/holds (generated from real category prices + availability ratio), snacks menu, payment/booking confirmation.
**Not built (no backend support):** login/onboarding, trailers, IMDb/Rotten Tomatoes scores, coming soon / reminders.
