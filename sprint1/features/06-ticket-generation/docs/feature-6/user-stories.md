# Feature #6 — Ticket Generation: User Stories

**Sprint:** Sprint 1  
**Feature:** Ticket Generation & Email Delivery  
**Assigned to:** Hari Sharma (https-hari)  
**Branch:** ticket-generation-hari  

---

## User Stories

---

### US-01 · Email Confirmation on Booking

**As a** registered user who has completed payment,  
**I want** to receive my booking confirmation and ticket via email,  
**So that** I have a permanent record of my booking without needing to log back in.

**Acceptance Criteria:**
- [ ] After a successful booking, the system sends an email to the address provided by the user
- [ ] The email contains the event name, date, time, venue, seat details, and total amount paid
- [ ] The email is sent from the platform's official address (`hs9998706@gmail.com`)
- [ ] The email is delivered within 30 seconds of booking confirmation
- [ ] If email delivery fails, the booking is still confirmed and the user sees a fallback message on screen

---

### US-02 · PDF Ticket with QR Code

**As a** user who has booked a ticket,  
**I want** my ticket to be a downloadable PDF containing a QR code,  
**So that** I can show it at the venue for entry verification without requiring internet access.

**Acceptance Criteria:**
- [ ] The PDF ticket is auto-generated immediately after booking confirmation
- [ ] The PDF includes: event name, date, time, venue, seat row and number, tier, price, and booking ID
- [ ] A unique QR code is embedded in the PDF, encoding the booking ID and transaction ID
- [ ] The QR code is scannable by a standard QR reader
- [ ] The PDF is attached to the confirmation email
- [ ] The PDF is also available for download from the confirmation page

---

### US-03 · On-Screen Booking Confirmation

**As a** user who has just completed a booking,  
**I want** to see a confirmation screen with my ticket details immediately,  
**So that** I have instant visual proof of my booking without waiting for an email.

**Acceptance Criteria:**
- [ ] After the API returns a successful response, the confirmation page displays the ticket card
- [ ] The ticket card shows: event name, venue, date, time, seat details, booking ID, transaction ID, and payment status
- [ ] The page indicates whether the confirmation email was successfully sent
- [ ] A "Download PDF" button is present and functional
- [ ] The page shows a loading state while the ticket is being generated

---

### US-04 · Dynamic Email Address Input

**As a** user going through the booking flow,  
**I want** to enter the email address where I want my ticket sent,  
**So that** I can choose to receive the ticket on any email, not just my account email.

**Acceptance Criteria:**
- [ ] Before the booking is confirmed, the user is shown a form to enter their email address
- [ ] The email field validates the format before submission
- [ ] The system uses the entered email as the recipient for ticket delivery
- [ ] The confirmation screen displays the email address the ticket was sent to

---

### US-05 · Idempotent Booking Confirmation

**As a** system,  
**I want** repeated confirmation requests for the same booking ID to return the same ticket,  
**So that** duplicate API calls (due to retries or network issues) do not generate duplicate tickets or send duplicate emails.

**Acceptance Criteria:**
- [ ] If `POST /bookings/confirm` is called again with the same `booking_id`, the existing ticket is returned
- [ ] No duplicate email is sent on repeat calls
- [ ] The response is identical to the original confirmation response
- [ ] The HTTP status returned is `200 OK` (not `201`) for a repeated call

---

### US-06 · PDF Download on Demand

**As a** user on the confirmation page,  
**I want** to download my ticket PDF at any time,  
**So that** I can save it locally even if I didn't receive the email or want an extra copy.

**Acceptance Criteria:**
- [ ] A "Download PDF" button is visible on the confirmation page
- [ ] Clicking it triggers a browser file download of the ticket PDF
- [ ] The downloaded file is named `ticket_<booking_id>.pdf`
- [ ] The PDF is the same as the one attached to the email
- [ ] The download works via `GET /{booking_id}/pdf` on the backend

---

## Story Map Summary

| Story | Actor | Priority | Status |
|-------|-------|----------|--------|
| US-01 · Email Confirmation | User | Must Have | ✅ Done |
| US-02 · PDF with QR Code | User | Must Have | ✅ Done |
| US-03 · On-Screen Confirmation | User | Must Have | ✅ Done |
| US-04 · Dynamic Email Input | User | Must Have | ✅ Done |
| US-05 · Idempotent Booking | System | Should Have | ✅ Done |
| US-06 · PDF Download on Demand | User | Must Have | ✅ Done |
