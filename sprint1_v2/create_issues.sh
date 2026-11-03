#!/bin/bash
# Run this from the repo root after: gh auth login
# Creates all open issues for sprint1_v2 integration branch

REPO="VTSLM/Show-Ticket-Booking-System"
LABEL="sprint1_v2"

echo "Creating GitHub issues for sprint1_v2..."

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] Ticket PDF download flow needs end-to-end testing" \
  --body "## Problem
After payment is verified, the frontend calls:
1. \`POST /api/tickets/bookings/{booking_id}/confirm\` — generates ticket + sends email
2. \`GET  /api/tickets/bookings/{booking_id}/pdf\` — downloads PDF

These endpoints have not been tested end-to-end after a real Razorpay test payment.

## What to test
- Complete a payment using Razorpay Netbanking test mode (any bank, any credentials)
- Check that booking status changes to \`confirmed\` in Supabase
- Check that a row is inserted into the \`tickets\` table
- Check that PDF downloads successfully

## Files
- \`sprint1_v2/backend/routers/tickets.py\`
- \`sprint1_v2/backend/services/ticket_service.py\`
- \`sprint1_v2/backend/services/qr_service.py\`

## Prerequisite
Run this SQL in Supabase before testing (tickets table must exist):
\`\`\`sql
CREATE TABLE IF NOT EXISTS tickets (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id   uuid NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
    user_id      uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    show_id      uuid NOT NULL REFERENCES shows(id) ON DELETE RESTRICT,
    qr_code_data text,
    status       varchar(20) NOT NULL DEFAULT 'valid',
    is_used      boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);
\`\`\`"

echo "✓ Issue 1 created"

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] Wrong tickets migration — 002_tickets_f6.sql conflicts with backend" \
  --body "## Problem
\`sprint1/features/06-ticket-generation/backend/migrations/002_tickets_f6.sql\` creates a \`tickets\` table with completely different columns than what \`sprint1_v2/backend/routers/tickets.py\` expects.

**F6 migration has:** \`booking_number, user_name, event_name, seats (jsonb), ...\`  
**Backend router uses:** \`booking_id (FK), user_id (FK), show_id (FK), qr_code_data, status, is_used\`

## Fix
Do NOT run the F6 migration. Instead run this SQL in Supabase:
\`\`\`sql
CREATE TABLE IF NOT EXISTS tickets (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id   uuid NOT NULL REFERENCES bookings(id) ON DELETE RESTRICT,
    user_id      uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    show_id      uuid NOT NULL REFERENCES shows(id) ON DELETE RESTRICT,
    qr_code_data text,
    status       varchar(20) NOT NULL DEFAULT 'valid',
    is_used      boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);
\`\`\`

## Long-term
Either rewrite \`tickets.py\` to match the F6 schema, or update the F6 migration to match the router."

echo "✓ Issue 2 created"

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] Email ticket delivery not tested / Gmail App Password required" \
  --body "## Problem
Ticket confirmation emails are sent via Gmail SMTP in \`sprint1_v2/backend/services/email_service.py\`.  
Each developer needs to set up their own Gmail App Password to test this locally.

## Setup steps
1. Go to myaccount.google.com → Security → 2-Step Verification → App passwords
2. Generate an app password for 'Mail'
3. Add to \`backend/.env\`:
\`\`\`
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
\`\`\`

## Note
Email failure is non-fatal — the ticket confirm endpoint catches the exception and still returns success. So the booking flow works even if email is not configured; the user just won't receive an email.

## To test
After a successful payment, check that the confirmation email arrives in the inbox set in \`GMAIL_USER\`."

echo "✓ Issue 3 created"

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] UPI payment option not showing in Razorpay test modal" \
  --body "## Problem
The Razorpay payment modal only shows Cards, Netbanking, and Wallet options. UPI (the most reliable test option using \`success@razorpay\`) is not visible.

## Impact
Developers testing the payment flow must use Netbanking or the specific test card:
- **Netbanking:** Select any bank → any credentials → Submit (works 100% in test mode)
- **Card:** \`5267 3181 8797 5449\` / Expiry: \`12/28\` / CVV: \`123\` / OTP: \`1234\`
- Do NOT use \`4111 1111 1111 1111\` — fails with 'international card not supported'

## Possible fix
Check Razorpay Dashboard → Settings → Payment Methods → enable UPI for test mode."

echo "✓ Issue 4 created"

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] Manager dashboard (/manager) needs testing" \
  --body "## Problem
The manager dashboard at \`/manager\` (frontend) and corresponding backend routes in \`sprint1_v2/backend/routers/manager.py\` have not been tested in the integrated environment.

## What to test
- Login as a user with the \`manager\` role
- Create a venue, screen, event, and show
- Verify the show appears in the browse page
- Verify seat layout is generated correctly

## How to assign manager role
\`\`\`sql
INSERT INTO user_roles (user_id, role_id)
SELECT '<user-uuid>', id FROM roles WHERE code = 'manager'
ON CONFLICT DO NOTHING;
\`\`\`

## Files
- \`sprint1_v2/frontend/app/manager/page.tsx\`
- \`sprint1_v2/backend/routers/manager.py\`"

echo "✓ Issue 5 created"

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] Admin dashboard (/admin) needs testing" \
  --body "## Problem
The admin panel at \`/admin\` has not been tested in the integrated environment.

## What to test
- Login as a user with the \`admin\` role
- View user list
- Change user roles / status

## How to assign admin role
\`\`\`sql
INSERT INTO user_roles (user_id, role_id)
SELECT '<user-uuid>', id FROM roles WHERE code = 'admin'
ON CONFLICT DO NOTHING;
\`\`\`

## Files
- \`sprint1_v2/frontend/app/admin/page.tsx\`"

echo "✓ Issue 6 created"

gh issue create \
  --repo "$REPO" \
  --title "[sprint1_v2] Seat locks expire silently — no background cleanup job" \
  --body "## Problem
Seats are locked for 5 minutes when a user selects them. After expiry, the \`locked_until\` timestamp passes but the seat \`status\` stays as \`'locked'\` in the DB until some other request queries it.

There is no background job (cron/celery) to sweep expired locks and reset them to \`'available'\`.

## Impact
- Other users trying to book the same show will see stale locked seats
- The lock expiry check only happens reactively (when the seat is queried)

## Possible fix
Add a periodic SQL cleanup function or a FastAPI background task:
\`\`\`sql
UPDATE show_seats
SET status = 'available', locked_by = NULL, locked_until = NULL
WHERE status = 'locked' AND locked_until < now();
\`\`\`

Or call this at the start of every \`GET /api/seats/{show_id}\` request."

echo "✓ Issue 7 created"

echo ""
echo "All 7 issues created successfully!"
