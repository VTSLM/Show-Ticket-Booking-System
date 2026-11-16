# Reviews frontend integration

This frontend is the existing TicketFlow Next.js application with the Reviews & Ratings UI integrated.

## Added files
- `app/events/[eventId]/reviews/page.tsx` — event reviews page.
- `lib/reviewsApi.ts` — Reviews API client.

## Updated file
- `app/browse/page.tsx` — adds a separate Reviews & Ratings link to each show card. The link uses `event_id` from the browse API response; booking continues to use `show_id`.

## Run
From this directory, run `npm install` and `npm run dev`. Configure `NEXT_PUBLIC_API_URL` in `.env.local` to point to your FastAPI backend (defaults to `http://localhost:8000`).

The Reviews page requires the corresponding Reviews backend endpoints and database migrations to be deployed for live data and write actions.
