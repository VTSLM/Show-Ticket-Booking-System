# Changelog

All notable changes to TicketFlow are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org). Each version matches one sprint; the [GitHub releases](https://github.com/VTSLM/Show-Ticket-Booking-System/releases) list owners and pull requests.

## [Unreleased] (Sprint 3)

### Added
- Wishlist for saving shows (#79)
- Single app layout at the repo root, ordered database migrations, Terraform layout for Azure (#83)
- Project documentation, logo, MIT license, contribution workflow, issue and PR templates (#84)
- Stricter CI with tests, linting, migration checks, secret scanning, CodeQL and Dependabot (#85)

### Removed
- Duplicated `sprint1/`, `sprint2/` and `sprint3/` folders. Earlier sprints are available as the `v0.1.0` and `v0.2.0` tags.

### Security
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
