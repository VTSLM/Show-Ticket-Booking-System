# Changelog

All notable changes to TicketFlow are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org). Each version matches one sprint; the [GitHub releases](https://github.com/VTSLM/Show-Ticket-Booking-System/releases) list owners and pull requests.

## [Unreleased] (Sprint 3)

### Added
- Managers can enter and edit every event detail: description, genre, poster and backdrop upload with preview, cast and crew for movies, artists for live events, release date, certificate and formats for movies only, and terms and conditions (#169)
- Demo catalogue seed: 10 cities, multiplexes, arenas, auditoriums and comedy clubs with matching seat maps, 10 movies, live events and a week of showtimes; posters are served from the `demo-posters` storage bucket (`database/seeds/005_demo_catalogue.py`, #191)
- Admin → Users: list and search all users, give or remove the manager and admin roles, block and unblock accounts with a required reason; every change, including manager approvals, is recorded in an audit log (#138)
- TicketFlow Assistant: a chat widget that finds shows, shows details, seats, reviews and recommendations, answers questions about the user's own bookings and wishlist, explains policies, and replies in English, Hindi or Gujarati. Read-only; nothing is stored
- Wishlist for saving shows (#79)
- Single app layout at the repo root, ordered database migrations, Terraform layout for Azure (#83)
- Project documentation, logo, MIT license, contribution workflow, issue and PR templates (#84)
- Stricter CI with tests, linting, migration checks, secret scanning, CodeQL and Dependabot (#85)

### Changed
- The TicketFlow Assistant is for logged-in users only: guests who open it see a "Log in to use the TicketFlow AI Assistant" notification with a Log in link, and the chat endpoints return 401 without a login (#204)
- Sign-up: Confirm Password must be typed (copy, cut, paste and drag-and-drop are blocked in that field only) and shows whether the passwords match while typing (#136)

### Removed
- Duplicated `sprint1/`, `sprint2/` and `sprint3/` folders. Earlier sprints are available as the `v0.1.0` and `v0.2.0` tags.

### Fixed
- New events no longer get invented IMDb, Metacritic, match and age-rating scores, and live events no longer get a film certificate (#169)
- Coupon routes are covered by a test so they cannot silently go missing; the "resource not found" in #197 came from a backend that did not have them yet (#197)
- Stadium and arena seat maps show curved tiers round the stage, with the Fan Pit and standing floor as rings in front of it (front stage) or around it (center stage), instead of a cinema grid (#198)
- Event page city buttons no longer run past the card or put the pin above the name, and the page starts on the user's own city instead of the first city in the list (#193)
- Cancel dialog showed "0 Ticket(s)" and "General Admission" for seated bookings; it now lists the seats and counts standing passes
- Guests no longer see a hold timer for seats that are not actually held; they are asked to log in to hold them
- Customers no longer see the internal event status, and live events say "venues" instead of "theatres"
- Cinema seats are no longer labelled "Grandstand"
- Events without a working poster show a neutral placeholder for their event type instead of the Ramayana poster (#170)
- Notifications have a close button; the red icon on error toasts looked like one but did nothing
- Browse city list shows only cities with upcoming shows, so empty or test venues no longer appear (#191)
- Booking seats or standing-zone tickets no longer fails with a server error: bookings now store their subtotal and discount, and the zone booking query is fixed (#174)
- Malformed ids in URLs return 404 instead of a server error, and the seat map of an unknown show returns 404 instead of an empty map (#140)
- Concerts, theatre, comedy and sports events no longer show cinema formats (2D, IMAX) or a cinema screen on the seat map; movies offer only the formats their showtimes have, and managers are warned when a screen's layout does not fit the event (#168)

### Security
- Frontend sends X-Frame-Options, frame-ancestors, nosniff, Referrer-Policy and Permissions-Policy headers; the public ticket check no longer returns the internal ticket id
- The backend now trusts only Firebase ID tokens that the Firebase Admin SDK verifies
- Only active accounts can use the API; pending and blocked accounts are refused on every request, not only at login
- The support inbox is limited to admins
- Upgraded Next.js to 14.2.35
- Upgraded FastAPI (Starlette 1.x), Pillow, python-multipart and python-dotenv for security fixes; pinned `openai`
- Production settings: `APP_ENV=production` checks required settings at startup, hides the API docs and verifies the database certificate; CORS origins come from `CORS_ORIGINS`; the rate limiter reads the client IP the proxy added
- Removed a committed virtual environment, a committed `.env` file and leaked credentials from git history.

## [0.2.0] - 2026-11-16 (Sprint 2)

### Added
- Critics and reviews: write, edit and delete reviews, comments, helpful votes, spoiler flag, critic and audience sections, reporting, verified attendee badge, AI summaries
- Browse: fuzzy search, sorting, sections per event type, image placeholders
- Venue verification with admin review and mandatory rejection reasons
- Registration security: birthdate, confirm password, strong password rules, forgot password
- Organizer verification with PAN, GSTIN and IFSC validation and a private document vault
- Show details and flexible venue layouts (cinema, concert stage, fan pit, standing zones, stadium) with terms and conditions before payment
- Customer care: help centre, support requests, conversation threads, admin replies by email
- Ticket cancellation with a 2-hour cutoff and Razorpay refunds
- Profile editing with photo upload, and per-show dynamic seat pricing
- Admin invite-code registration
- pytest and Playwright test suites

### Fixed
- Seat lock cleanup, draft shows visible in browse, payment verification and receipt bugs, auth route guards, Razorpay startup and checkout retry

## [0.1.0] - 2026-11-06 (Sprint 1)

### Added
- User authentication with User, Manager and Admin roles (Firebase)
- Manager show listing for venues, events and schedules
- Browse and search shows
- Seat selection with temporary seat locks
- Razorpay payment gateway in test mode
- PDF e-tickets with QR codes and email delivery
- Integrated FastAPI and Next.js application

[Unreleased]: https://github.com/VTSLM/Show-Ticket-Booking-System/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/VTSLM/Show-Ticket-Booking-System/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VTSLM/Show-Ticket-Booking-System/releases/tag/v0.1.0
