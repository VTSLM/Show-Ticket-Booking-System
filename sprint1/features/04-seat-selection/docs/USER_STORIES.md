# Product Backlog: User Stories — Feature 04 (Seat Selection & Allocation)

**Project:** Show Ticket Booking System  
**Sprint:** Sprint 1  
**Feature:** Feature 04 — Seat Selection & Allocation (Person 2)  
**Branch:** `seat-allocation-khushi`  
**Document Type:** Agile Product Backlog (Front of Card / Back of Card)

---

## Backlog Summary & Traceability Matrix

| Story ID | Title | Requirement Ref | Priority | Story Points |
| :--- | :--- | :--- | :--- | :---: |
| **US-01** | Visual Seat Map & Pricing Tier Rendering | Registered User FR / Guest FR | High (Must Have) | 5 |
| **US-02** | Multi-Seat Selection & Price Calculation with Cap | Registered User FR | High (Must Have) | 3 |
| **US-03** | Atomic Seat Locking (Compare-And-Swap) | Registered User FR / NFR | Critical (Must Have) | 8 |
| **US-04** | 5-Minute Hold Countdown & Auto-Expiry Sweeper | Registered User NFR / FR | High (Must Have) | 5 |
| **US-05** | User-Initiated Manual Hold Release | Registered User FR | Medium (Should Have) | 2 |
| **US-06** | Post-Payment Booking Confirmation & Ticket Issuance | Registered User FR | High (Must Have) | 5 |
| **US-07** | Real-Time Single-Seat Delta Broadcast via WebSocket | Phase 6 / Concurrency NFR | High (Must Have) | 8 |
| **US-08** | Booking Cancellation & Inventory Pool Recovery | FR13 / Cancellation Policy | High (Must Have) | 5 |
| **US-09** | Expired Hold Recovery & Failure UX | Phase 7 UX / Error Handling | Medium (Should Have) | 3 |

---

## Detailed User Story Cards

---

### User Story US-01: Visual Seat Map & Pricing Tier Rendering

#### 📇 Front of the Card
* **User Story ID:** US-01
* **Title:** Interactive Visual Seat Map with Color-Coded Pricing Tiers
* **Priority:** High | **Story Points:** 5
* **User Persona:** Event Attendee / Ticket Buyer
* **Narrative:**
  * **As an** event attendee browsing a show,
  * **I want to** view an interactive, curved visual seat map with distinct color codes for each seating tier and clear visual indicators for seat availability,
  * **So that** I can easily identify the best seats that fit my budget and preferences before committing to a purchase.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 1.1 — Tier Color Coding:**
  * **Given** a user opens the seat selection page for a show,
  * **When** the seat map loads,
  * **Then** the system must render seats grouped by section with color-coded badges:
    * VIP Section: Purple accent (₹1,500)
    * Premium Section: Amber accent (₹900)
    * General Section: Cyan accent (₹400)
* **AC 1.2 — Status Distinctions:**
  * Available seats must render in an active selectable state.
  * Booked seats must render greyed-out with an occupied/sold indicator and disabled click actions.
  * Blocked seats (administrative/safety holds) must render greyed-out with a locked icon and disabled click actions.
* **AC 1.3 — Visual Cinema Orientation:**
  * The map must prominently display an illuminated curved cinema screen indicator (*"SCREEN THIS WAY"*) at the top to give users spatial orientation.
* **AC 1.4 — Responsive Layout:**
  * The seat grid must fit within mobile and desktop viewports without broken alignment.

---

### User Story US-02: Multi-Seat Selection & Price Calculation with Cap Enforcement

#### 📇 Front of the Card
* **User Story ID:** US-02
* **Title:** Dynamic Seat Selection, Real-Time Total Calculation, and Booking Cap Enforcement
* **Priority:** High | **Story Points:** 3
* **User Persona:** Event Attendee / Ticket Buyer
* **Narrative:**
  * **As an** event attendee,
  * **I want to** click to select or deselect multiple available seats and see an instant price breakdown while being prevented from exceeding the maximum booking limit,
  * **So that** I can review my total cost including taxes and avoid violating ticket purchase quotas.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 2.1 — Selection Toggle:**
  * **Given** an available seat on the grid,
  * **When** the user clicks the seat,
  * **Then** the seat changes to the "Selected" state (neon emerald glow) and is added to the selection list in the checkout sidebar.
  * **When** clicked again, it must deselect and be removed from the sidebar list.
* **AC 2.2 — Live Price Breakdown:**
  * The sidebar must dynamically calculate and display:
    * Base ticket subtotal = $\sum (\text{selected seat prices})$
    * Taxes & Convenience fees (standard calculated rate)
    * Grand Total in INR (₹)
* **AC 2.3 — Cap Enforcement (Max 6 Seats):**
  * **Given** a user has already selected 6 seats,
  * **When** the user attempts to select a 7th seat,
  * **Then** the system must reject the selection, prevent the seat from turning active, and display a warning toast: *"Cannot book more than 6 seats at once."*

---

### User Story US-03: Atomic Seat Locking (Compare-And-Swap)

#### 📇 Front of the Card
* **User Story ID:** US-03
* **Title:** Atomic Compare-And-Swap (CAS) Seat Hold
* **Priority:** Critical | **Story Points:** 8
* **User Persona:** System Backend / Concurrent Ticket Buyers
* **Narrative:**
  * **As a** platform architect and event attendee,
  * **I want the system to** execute an atomic all-or-nothing hold on my selected seats using a Compare-and-Swap (CAS) mechanism,
  * **So that** no two concurrent users can lock or purchase the exact same seat simultaneously, eliminating double-booking race conditions.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 3.1 — Atomic All-or-Nothing Guarantee:**
  * **Given** User A requests to hold seats `[V1-S1, V1-S2]`,
  * **When** the hold request is processed,
  * **Then** the backend must verify availability and update the status to `locked` in a single indivisible step.
* **AC 3.2 — Conflict Rollback:**
  * **Given** User A and User B simultaneously attempt to lock seat `V1-S1`,
  * **When** User A's transaction succeeds,
  * **Then** User B's lock request must fail immediately with HTTP `409 Conflict` returning `failed_seat_ids: ["V1-S1"]`.
  * **Crucial Invariant:** If User B requested `[V1-S1, V1-S2]`, seat `V1-S2` must NOT be locked for User B (zero partial locks; all-or-nothing rollback).
* **AC 3.3 — Lock Ownership & Expiry Record:**
  * Upon successful lock, the record must store `status = 'locked'`, `locked_by = userId`, and `expires_at = now + 5 minutes`.

---

### User Story US-04: 5-Minute Hold Countdown & Auto-Expiry Sweeper

#### 📇 Front of the Card
* **User Story ID:** US-04
* **Title:** Server-Authoritative 5-Minute Hold Timer & Background Expiry Sweeper
* **Priority:** High | **Story Points:** 5
* **User Persona:** Event Attendee & System Maintenance Process
* **Narrative:**
  * **As a** ticket buyer with locked seats,
  * **I want to** see an accurate 5-minute countdown timer reflecting my remaining hold duration,
  * **And as the** platform, I want a background sweeper to automatically release abandoned seats back into the available pool when the hold expires,
  * **So that** inventory is never held indefinitely by inactive users.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 4.1 — Server-Authoritative Countdown:**
  * **Given** a user successfully locks seats,
  * **When** the checkout sidebar is displayed,
  * **Then** the timer must calculate remaining time against the server-issued `expires_at` ISO-8601 timestamp (preventing client-side tampering or tab-freeze drift).
* **AC 4.2 — Background Sweeper Loop:**
  * The backend must run an asynchronous background job every 30 seconds inspecting active locks.
  * Any seat where `current_utc_time > expires_at` and `status == 'locked'` must be reverted to `status = 'available'`, `locked_by = null`, `expires_at = null`.
* **AC 4.3 — Expiry Broadcast:**
  * When the sweeper releases expired seats, it must broadcast a release notification via WebSocket so all active viewers see the seats turn available.

---

### User Story US-05: User-Initiated Manual Hold Release

#### 📇 Front of the Card
* **User Story ID:** US-05
* **Title:** Manual Cancellation of In-Progress Seat Hold
* **Priority:** Medium | **Story Points:** 2
* **User Persona:** Ticket Buyer
* **Narrative:**
  * **As an** event attendee who changes their mind during seat holding,
  * **I want to** manually release my held seats via a "Release Hold" / "Cancel Selection" button,
  * **So that** the seats immediately become available for other customers without waiting for the 5-minute timer to elapse.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 5.1 — Manual Release Endpoint:**
  * **Given** a user has active locked seats,
  * **When** the user clicks "Release Hold",
  * **Then** the client sends a `POST /api/seats/release` request with `seat_ids` and `user_id`.
* **AC 5.2 — Authorization Check:**
  * The backend must only release seats whose `locked_by` matches the requesting `user_id`.
* **AC 5.3 — Immediate Inventory Return:**
  * The released seats must immediately revert to `available` state in the database and emit a real-time update to all active viewers.

---

### User Story US-06: Post-Payment Booking Confirmation & Ticket Issuance

#### 📇 Front of the Card
* **User Story ID:** US-06
* **Title:** Booking Confirmation and Unique QR E-Ticket Generation
* **Priority:** High | **Story Points:** 5
* **User Persona:** Ticket Buyer & Event Organizer
* **Narrative:**
  * **As an** event attendee who has successfully completed payment,
  * **I want the system to** atomically transition my locked seats to booked status and generate a confirmed booking with a unique reference and digital QR code,
  * **So that** I have official, verifiable proof of entry for the event.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 6.1 — Pre-Confirmation Lock Validation:**
  * **Given** a payment success callback reaches the confirmation endpoint,
  * **When** `POST /api/seats/confirm` is invoked,
  * **Then** the backend must re-verify that the seats are still locked by this user and that `current_utc_time <= expires_at`.
* **AC 6.2 — Atomic State Transition:**
  * If valid, transition `status = 'booked'`, `locked_by = null`, `expires_at = null`.
* **AC 6.3 — Booking Record Generation:**
  * Create a persistent booking record containing:
    * Unique Booking ID (e.g., `BKG-00001`)
    * User ID, Show ID, and Seat IDs
    * Total amount paid and UTC timestamp
* **AC 6.4 — Digital Confirmation Screen:**
  * The frontend must render a confirmation screen featuring the booking ID, seat summary, download/save options, and a unique QR entry code.

---

### User Story US-07: Real-Time Seat Status Synchronization via WebSocket

#### 📇 Front of the Card
* **User Story ID:** US-07
* **Title:** Real-Time Single-Seat Delta Updates for Concurrent Viewers
* **Priority:** High | **Story Points:** 8
* **User Persona:** Concurrent Ticket Buyers
* **Narrative:**
  * **As an** active ticket buyer looking at a show's seat map,
  * **I want to** receive instant real-time visual updates whenever any seat is locked, released, or booked by another user,
  * **So that** I always see live inventory without needing to manually refresh the page or polling the entire layout.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 7.1 — Lightweight Delta Protocol:**
  * **Given** any seat state change (`locked`, `available`, `booked`),
  * **When** the event is broadcast over WebSocket (`/ws/{show_id}`),
  * **Then** the server must send only the changed seat payload:
    ```json
    { "type": "SEAT_UPDATE", "seat_id": "G1-S3", "status": "locked" }
    ```
    (The server must NOT broadcast the entire seat layout).
* **AC 7.2 — Non-Disruptive Frontend State Update:**
  * The client must update only that specific seat's state in memory.
  * The update must NOT unmount the grid or deselect seats currently in the user's active selection.
* **AC 7.3 — Auto-Reconnection:**
  * If the WebSocket connection drops, the frontend hook must attempt automatic reconnection within 3 seconds.

---

### User Story US-08: Booking Cancellation & Inventory Pool Recovery (FR13)

#### 📇 Front of the Card
* **User Story ID:** US-08
* **Title:** Self-Service Booking Cancellation and Immediate Seat Pool Return
* **Priority:** High | **Story Points:** 5
* **User Persona:** Registered Attendee
* **Narrative:**
  * **As a** registered attendee with a confirmed booking,
  * **I want to** view my booking history and cancel an eligible booking,
  * **So that** I can initiate a refund and release my seats back into the available pool for other fans (Requirement FR13).

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 8.1 — User Booking Dashboard:**
  * **Given** an authenticated user navigates to "My Bookings",
  * **When** the page loads,
  * **Then** all active and historical bookings for that user are displayed with booking ID, date, seats, amount, and status.
* **AC 8.2 — Cancellation Execution:**
  * **When** the user clicks "Cancel Booking & Refund",
  * **Then** `POST /api/bookings/cancel` is invoked with `booking_id` and `user_id`.
* **AC 8.3 — Inventory Pool Restoration (FR13):**
  * The booking status transitions to `cancelled`.
  * All associated seats atomically transition from `booked` back to `available`.
  * A WebSocket broadcast is emitted immediately notifying all active viewers that those seats are free to book.

---

### User Story US-09: Graceful Failure Handling for Expired Seat Holds

#### 📇 Front of the Card
* **User Story ID:** US-09
* **Title:** Clear Failure Handling & Redirect for Expired Holds
* **Priority:** Medium | **Story Points:** 3
* **User Persona:** Ticket Buyer (Encountering Session Timeout)
* **Narrative:**
  * **As an** event attendee whose seat hold expired before completing checkout,
  * **I want to** receive a clear explanation and be smoothly redirected back to the seat map with expired seats clearly marked,
  * **So that** I am never silently charged for seats I no longer hold and can quickly re-select new seats.

#### 📝 Back of the Card (Conditions of Satisfaction / Acceptance Criteria)
* **AC 9.1 — Backend Rejection on Expired Confirm:**
  * **Given** a user's 5-minute hold has expired,
  * **When** they attempt to confirm payment,
  * **Then** the backend must reject the request with HTTP `409 Conflict` and error code `LOCK_EXPIRED`.
* **AC 9.2 — Dedicated Expired UX Screen:**
  * The frontend must intercept `LOCK_EXPIRED` and render the **Expired Hold Screen**:
    * Explains clearly: *"Your seat hold expired after 5 minutes of inactivity to keep ticket sales fair."*
    * Highlights which seats were released.
    * Provides a direct button: *"Return to Seat Map"*.
* **AC 9.3 — Fresh Inventory Fetch:**
  * Clicking return must trigger a fresh fetch of the seat layout, showing previously held seats as greyed out if another user grabbed them in the interim.
