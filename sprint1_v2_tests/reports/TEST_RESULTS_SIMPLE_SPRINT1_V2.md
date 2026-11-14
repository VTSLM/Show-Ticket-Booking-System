# TicketFlow Test Report (`sprint1_v2`)

> **Modules Tested:** Manager Listing, Payment Gateway, Ticket Generation  
> **Overall Result:** 24 Checks Passed, 8 Checks Failed *(plus TypeScript check passed)*

---

## Before You Read (How Tests Were Run)

Because this computer had no internet/database connection while testing, the automated tests simulated the database, Razorpay, and Gmail email server instead of hitting the live servers. The **actual FastAPI backend code** ran for every API test, and the **frontend code** passed its TypeScript type check (`npx tsc --noEmit`).

---

## Quick Scoreboard

| Feature | Passed | Failed | Overall Status |
| :--- | :---: | :---: | :--- |
| **1. Manager Listing** | 12 | 2 | Mostly working, but shows stay hidden from Browse |
| **2. Payment Gateway** | 4 | 4 | Needs fixes before real users pay |
| **3. Ticket Generation** | 8 | 2 | Core QR/PDF/Email works, needs 2 security/error fixes |
| **Frontend Build Check** | 1 | 0 | No TypeScript code errors |

---

## 1. Manager Listing (Venues, Screens, Movies & Shows)

Files checked: [manager.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/routers/manager.py), [browse.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/routers/browse.py), [page.tsx](file:///d:/Sem%205/Se_project/sprint1_v2/frontend/app/manager/page.tsx), [api.ts](file:///d:/Sem%205/Se_project/sprint1_v2/frontend/lib/api.ts)

### What Passed
| Test | What Was Checked | Result |
| :--- | :--- | :---: |
| Create Venue | Adding a new theatre/venue saves properly | PASS |
| Missing Venue Info | Trying to add a venue without name/city is blocked | PASS |
| Create Screen with Seats | Adding a screen (2 rows × 10 seats) auto-creates 20 seats | PASS |
| Create Screen (Capacity Only) | Adding a screen without row/column numbers still works | PASS |
| Create Show & Seats | Creating a show creates the show and fills seats automatically (even if the screen had no seats yet) | PASS |
| Bad Show Times | Blocking a show where end time is before start time | PASS |
| Overlapping Shows | Blocking two shows scheduled on the same screen at the same time | PASS |
| Publish via API | Updating a movie status to `published` makes its shows appear on Browse | PASS |
| Role Protection | Blocking normal customers and logged-out users from manager pages/APIs | PASS |
| Delete Show | Admin can delete an unbooked show, and cannot delete a show that already has bookings | PASS |

### What Failed (Bugs Found)
1. **Shows created in Manager Dashboard don't show up on Browse Shows (`TC-MAN-BROWSE-01`)**
   - **Why in simple words:** When you create a movie in `/manager`, it is saved as a **`draft`** by default. There is no **"Publish"** button or dropdown in the Manager page, and the Browse page only shows movies marked **`published`**.
2. **Draft shows can still be opened directly by link (`TC-MAN-NFR03`)**
   - **Why in simple words:** Even though a `draft` movie is hidden from the Browse list, someone who knows the show's ID link can still load its details page (`GET /api/browse/shows/{show_id}`).
3. **Extra note found while reading the code:**
   - If a show has no seat records, Browse Shows returns a blank price (`null`) instead of falling back to the show's `base_price`.

---

## 2. Payment Gateway (Razorpay Checkout & Receipts)

Files checked: [payments.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/routers/payments.py), [page.tsx](file:///d:/Sem%205/Se_project/sprint1_v2/frontend/app/payment/page.tsx), [001_initial_schema.sql](file:///d:/Sem%205/Se_project/sprint1/database/migrations/001_initial_schema.sql), [002_payment_gateway.sql](file:///d:/Sem%205/Se_project/sprint1/database/migrations/002_payment_gateway.sql)

### What Passed
| Test | What Was Checked | Result |
| :--- | :--- | :---: |
| Start Payment | Creating a Razorpay order converts ₹500.00 to `50000` paise correctly | PASS |
| Block Paid Bookings | Rejecting a new payment order if the booking is already paid/confirmed | PASS |
| Fake Payment Check | Blocking a payment if the security signature is fake or altered | PASS |
| Real Payment Update | Valid payment marks the booking `confirmed`, locks the seats as `booked`, saves the payment, and builds a receipt number | PASS |

### What Failed (Bugs Found)
1. **Viewing a receipt crashes (`TC-PAY-008`) — Critical**
   - **Why in simple words:** The API to look up a receipt (`GET /api/payments/receipts/{receipt_number}`) asks the database for a `booking_id` column inside the `receipts` table, but the `receipts` table doesn't have that column (it uses `payment_id` instead).
2. **Anyone logged in can trigger verification on another person's booking (`TC-PAY-IDOR-VERIFY`) — Critical Security**
   - **Why in simple words:** When verifying payment (`POST /api/payments/orders/{booking_id}/verify`), the backend does not check if the logged-in user actually owns that booking, or if the Razorpay order actually belongs to that booking.
3. **Retrying payment after closing the popup fails (`TC-PAY-RETRY`) — High**
   - **Why in simple words:** If a user clicks **Pay**, closes the Razorpay window without paying, and clicks **Pay** again, the database blocks creating a second payment order for the same unpaid booking.
4. **Decimal amounts can lose 1 paisa (`TC-PAY-PAISE`) — Major**
   - **Why in simple words:** Converting rupees to paise uses `int(float(...) * 100)` instead of rounding, so `₹19.99` becomes `1998` paise instead of `1999` paise.
5. **Extra note found while reading the frontend code:**
   - If payment verification fails on the payment screen, the **Pay** button stays stuck in a loading state until the page is refreshed.

---

## 3. Ticket Generation (QR Code, PDF, Email & Entry Scan)

Files checked: [tickets.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/routers/tickets.py), [qr_service.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/services/qr_service.py), [ticket_service.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/services/ticket_service.py), [email_service.py](file:///d:/Sem%205/Se_project/sprint1_v2/backend/services/email_service.py), [page.tsx](file:///d:/Sem%205/Se_project/sprint1_v2/frontend/app/payment/page.tsx)

### What Passed
| Test | What Was Checked | Result |
| :--- | :--- | :---: |
| QR Image Creation | Creating a valid PNG QR image for the booking | PASS |
| PDF File Creation | Generating a valid 6 KB PDF file (both with full info and missing optional info) | PASS |
| Block Unpaid Confirm | Rejecting ticket confirmation if the booking is still unpaid (`pending`) | PASS |
| Double-Click Protection | Clicking confirm twice returns the same ticket instead of making a duplicate | PASS |
| Email Failure Safety | If Gmail fails or is offline, the ticket is still saved and returned | PASS |
| Email Formatting & Send | Creating the confirmation email with the PDF attached and calling Gmail SMTP *(mocked)* | PASS |
| PDF Download | Downloading the ticket streams a proper `.pdf` attachment | PASS |
| Gate Scanner Check | Checking a ticket shows valid for unused tickets, and invalid for already-used or missing tickets | PASS |

### What Failed (Bugs Found)
1. **Unpaid bookings can still download a PDF ticket (`TC-TCK-SEC-PDF`) — High**
   - **Why in simple words:** While `/confirm` checks if the booking is paid, the PDF download link (`GET /api/tickets/bookings/{booking_id}/pdf`) does **not**. Someone with an unpaid `pending` booking can download a PDF ticket with a QR code without paying.
2. **Invalid ticket ID crashes the scanner endpoint (`TC-TCK-UUID`) — Medium**
   - **Why in simple words:** Sending a garbled or non-UUID booking ID to `/verify` crashes with a database error instead of returning `{"valid": false}`.
3. **Extra notes found while reading the code:**
   - The downloaded PDF leaves out the venue city (`venue_city`), even though the emailed PDF includes it.
   - The gate check endpoint only checks if a ticket is valid — there is no button/endpoint yet to mark a ticket as **"used"** when scanned at the theatre door.
   - After payment succeeds in the frontend, if ticket creation/email fails, the error is silently hidden and the screen still tells the user `"Ticket emailed to you."`

---

## What Needs Fixing (Priority Order)

1. **Block unpaid PDF downloads** in `tickets.py` (`GET /pdf` should require `booking["status"] == "confirmed"`).
2. **Fix payment verification security** in `payments.py` (verify `user_id`, verify `razorpay_order_id` matches the booking, and fix `int(...)` -> `round(...)` for paise).
3. **Allow retrying payment** in `payments.py` (update/reuse existing unresolved payment order instead of hitting a duplicate-key error).
4. **Fix the receipt lookup query** in `payments.py` (join `payments` via `r.payment_id` instead of `r.booking_id`).
5. **Add a Publish button / status dropdown** for events in `/manager` so Managers & Admins can make shows appear on `/browse`, and hide `draft` shows from direct `/api/browse/shows/{show_id}` links.
6. **Handle bad UUIDs gracefully** in `/api/tickets/bookings/{booking_id}/verify`.
