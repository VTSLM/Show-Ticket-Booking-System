# Sequence Diagram: Customer Seat Selection and Booking Flow

## 1. Description and Purpose
This sequence diagram models the end-to-end customer booking scenario in TicketFlow, tracing the complete interaction across browser, Next.js frontend, FastAPI backend controllers, PostgreSQL database, Razorpay payment gateway, and Gmail SMTP service.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Browser)
    participant NextJS as Next.js Frontend
    participant SeatCtrl as seats.py (API)
    participant BookCtrl as bookings.py (API)
    participant PayCtrl as payments.py (API)
    participant TicketSvc as ticket_service.py
    participant DB as PostgreSQL 16
    participant Razorpay as Razorpay Gateway
    participant SMTP as Gmail SMTP Server

    %% Step 1: Open Show Details & Load Seat Map
    Customer ->> NextJS: Open /shows/{showId}/seats
    NextJS ->> SeatCtrl: GET /api/seats/{showId}/map (Optional Auth)
    SeatCtrl ->> DB: Clean expired locks (UPDATE show_seats)
    SeatCtrl ->> DB: Fetch show metadata, terms, seats, and zones
    SeatCtrl ->> DB: Fetch dynamic pricing parameters
    DB -->> SeatCtrl: Seat map data + multiplier
    SeatCtrl -->> NextJS: 200 OK (layout, seats with is_mine, zones, pricing)
    NextJS -->> Customer: Render interactive VenueLayoutCanvas

    %% Step 2: Customer selects and locks seats
    Customer ->> NextJS: Click seat (e.g., A1, A2)
    NextJS -->> Customer: Mark seat state 'pending' (amber pulse)
    NextJS ->> SeatCtrl: POST /api/seats/{showId}/lock {seat_ids: ["A1", "A2"]}
    
    alt Seats Available for Locking
        SeatCtrl ->> DB: Atomic UPDATE show_seats SET status='locked', locked_by=$user, locked_until=NOW()+10m WHERE status='available'
        DB -->> SeatCtrl: UPDATE 2
        SeatCtrl ->> DB: Freeze dynamic price (UPDATE locked_price)
        SeatCtrl ->> DB: pg_notify('seat_events', {type: 'lock', seat_ids: [...]})
        SeatCtrl -->> NextJS: 200 OK {locked: ["A1", "A2"], locked_until: ...}
        NextJS -->> Customer: Update seat state to 'mine' (blue), update subtotal
    else Lock Conflict (409 Conflict)
        SeatCtrl ->> DB: Rollback any partially acquired seats
        SeatCtrl -->> NextJS: 409 Conflict (Seats unavailable)
        NextJS -->> Customer: Restore seat state to 'locked', show toast error
    end

    %% Step 3: Checkout and Booking Creation
    Customer ->> NextJS: Proceed to Checkout (Enter Coupon, Accept Terms)
    NextJS ->> BookCtrl: POST /api/bookings {show_id, seat_ids, terms_accepted: true, coupon_code: "SAVE10"}
    BookCtrl ->> DB: Verify locked_by matches current_user AND locked_until > NOW()
    BookCtrl ->> DB: Check active coupon & compute discount
    BookCtrl ->> DB: INSERT INTO bookings (subtotal, discount, total, status='pending')
    BookCtrl ->> DB: INSERT INTO booking_seats (booking_id, show_seat_id, unit_price)
    BookCtrl ->> DB: Record terms acceptance (INSERT INTO terms_acceptances)
    DB -->> BookCtrl: Booking record created (UUID, booking_number)
    BookCtrl -->> NextJS: 200 OK {booking_id, total_amount, booking_number}

    %% Step 4: Payment Order Creation
    NextJS ->> PayCtrl: POST /api/payments/orders {booking_id}
    PayCtrl ->> Razorpay: Create Order (amount in paise, currency='INR', receipt=booking_number)
    Razorpay -->> PayCtrl: Razorpay Order {id: "order_xyz123"}
    PayCtrl ->> DB: INSERT INTO payment_orders (booking_id, razorpay_order_id, status='created')
    PayCtrl -->> NextJS: 200 OK {order_id: "order_xyz123", amount: ...}
    NextJS -->> Customer: Open Razorpay Checkout modal

    %% Step 5: Payment Processing & Verification
    Customer ->> Razorpay: Enter payment details & authorize
    
    alt Payment Authorized Successfully
        Razorpay -->> NextJS: Success payload {razorpay_payment_id, razorpay_order_id, razorpay_signature}
        NextJS ->> PayCtrl: POST /api/payments/orders/{bookingId}/verify {payment_id, order_id, signature}
        PayCtrl ->> PayCtrl: Verify HMAC SHA256 signature with RAZORPAY_KEY_SECRET
        PayCtrl ->> DB: INSERT INTO payments (status='successful', transaction_id)
        PayCtrl ->> DB: UPDATE bookings SET status='confirmed', booked_at=NOW()
        PayCtrl ->> DB: UPDATE show_seats SET status='booked' WHERE id IN (seats)
        PayCtrl ->> DB: INSERT INTO receipts (receipt_number, payment_id)
        PayCtrl ->> TicketSvc: generate_tickets_for_booking(booking_id)
        TicketSvc ->> DB: INSERT INTO tickets (status='valid', qr_code, ticket_number)
        TicketSvc ->> TicketSvc: Render PDF using ReportLab
        TicketSvc ->> SMTP: Send confirmation email with PDF attachment
        SMTP -->> Customer: Deliver Ticket PDF & QR to user email
        PayCtrl -->> NextJS: 200 OK {status: "confirmed", booking_id}
        NextJS -->> Customer: Redirect to /bookings/{bookingId} (Success confirmation)
    else Payment Failure / User Cancelled
        Razorpay -->> NextJS: Payment Dismissed / Failed
        NextJS ->> PayCtrl: Record failed attempt (status='failed')
        NextJS -->> Customer: Show payment failed error, allow retry before lock expires
    end
```

## 3. Important Implementation Notes
- **Non-Optimistic UI:** As implemented in `frontend/app/shows/[showId]/seats/page.tsx`, the frontend does not add the seat to `selectedSeatIds` until the HTTP 200 response returns from `/api/seats/{showId}/lock`. While pending, an amber pulsating indicator is displayed.
- **Atomic Availability Check:** The backend SQL query simultaneously checks availability and sets `locked_by` in a single atomic statement, preventing race conditions.
- **HMAC Verification:** The signature returned by Razorpay is cryptographically verified on the backend using `hmac.new(key, msg, hashlib.sha256)` before marking the booking as confirmed.
