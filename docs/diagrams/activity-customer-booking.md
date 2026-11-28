# Activity Diagram: End-to-End Customer Booking Workflow

## 1. Description and Purpose
Following UML 2.0 Activity Diagram principles from Lecture 21 (Activity Diagram, Saurabh Tiwari, DA-IICT), this diagram models the business process workflow of customer seat selection, locking, checkout, payment processing, ticket issuance, and error handling. It utilizes six vertical swimlanes to partition responsibilities across actors and subsystems, clearly distinguishing decision nodes, merge nodes, forks, and joins.

## 2. Activity Diagram with Swimlanes
```mermaid
flowchart TD
    %% Swimlanes
    subgraph Lane_Customer["Customer (Actor)"]
        A_Start((Start))
        A_Browse["Browse Shows & Select Show"]
        A_ViewMap["View Interactive Seat Map"]
        A_SelectSeat["Click to Select Seats"]
        A_ReviewCart["Review Cart & Enter Coupon"]
        A_AcceptTerms["Accept Terms & Conditions"]
        A_PayModal["Authorize Payment in Razorpay Modal"]
        A_ViewSuccess["View Booking Confirmation & Download Ticket"]
        A_End((End))
    end

    subgraph Lane_Frontend["Next.js Frontend (Presentation Subsystem)"]
        F_ReqMap["GET /api/seats/{id}/map"]
        F_MarkPending["Mark Seat 'Pending' (Amber Pulse)"]
        F_ReqLock["POST /api/seats/{id}/lock"]
        F_DecideLock{Lock<br/>Success?}
        F_MarkMine["Mark Seat 'Mine' (Blue) & Add to Cart"]
        F_RevertSeat["Clear Pending & Show Toast Error"]
        F_ReqBooking["POST /api/bookings"]
        F_ReqOrder["POST /api/payments/orders"]
        F_LaunchRazorpay["Open Razorpay Checkout Window"]
        F_DecidePayment{Payment<br/>Success?}
        F_ReqVerify["POST /api/payments/orders/{id}/verify"]
        F_ShowPaymentErr["Display Payment Error Toast"]
        F_RedirectSuccess["Redirect to /bookings/{id}"]
    end

    subgraph Lane_Backend["FastAPI Backend (Application Logic)"]
        B_FetchMap["Compute Dynamic Multiplier & Resolve Terms"]
        B_AtomicLock["Execute Atomic Lock UPDATE with 10m Window"]
        B_BroadcastLock["Broadcast Lock Event (WebSocket & pg_notify)"]
        B_ValidateBooking["Validate Held Seats & Apply Coupon Discount"]
        B_CreateOrder["Invoke Razorpay Order Creation API"]
        B_VerifyHMAC["Cryptographically Verify SHA-256 HMAC Signature"]
        B_ConfirmBooking["Update Booking 'confirmed' & Seat 'booked'"]
        B_TriggerTicket["Dispatch Asynchronous Ticket Generation"]
    end

    subgraph Lane_DB["PostgreSQL Database (Persistence Subsystem)"]
        D_ReleaseExpired["UPDATE show_seats (Release expired locks)"]
        D_ReadSeats["SELECT seats, show_seats, show_zones, dynamic_pricing"]
        D_RowLock["UPDATE show_seats SET status='locked', locked_by=UID"]
        D_InsertBooking["INSERT INTO bookings & booking_seats"]
        D_InsertOrder["INSERT INTO payment_orders"]
        D_CommitPayment["INSERT INTO payments, receipts & UPDATE bookings"]
        D_InsertTicket["INSERT INTO tickets (QR token, ticket_number)"]
    end

    subgraph Lane_Gateway["Razorpay Payment Gateway (External Subsystem)"]
        G_GenOrder["Generate Razorpay Order ID"]
        G_AuthCard["Authenticate Card / UPI / NetBanking"]
        G_ReturnSignature["Return Payment ID & HMAC Signature"]
    end

    subgraph Lane_Ticket["Ticket & Notification Service (Delivery Subsystem)"]
        T_RenderPDF["Render PDF Ticket via ReportLab Engine"]
        T_GenQR["Generate QR Code Image Payload"]
        T_SendMail["Deliver Confirmation Email via Gmail SMTP"]
    end

    %% Flow Connections
    A_Start --> A_Browse
    A_Browse --> F_ReqMap
    F_ReqMap --> B_FetchMap
    B_FetchMap --> D_ReleaseExpired
    D_ReleaseExpired --> D_ReadSeats
    D_ReadSeats --> F_ReqMap
    F_ReqMap --> A_ViewMap

    A_ViewMap --> A_SelectSeat
    A_SelectSeat --> F_MarkPending
    F_MarkPending --> F_ReqLock
    F_ReqLock --> B_AtomicLock
    B_AtomicLock --> D_RowLock
    D_RowLock --> B_AtomicLock

    B_AtomicLock --> F_DecideLock
    F_DecideLock -->|Yes: 200 OK| F_MarkMine
    B_AtomicLock -->|Fork: Sync Event| B_BroadcastLock
    F_DecideLock -->|No: 409 Conflict| F_RevertSeat
    F_RevertSeat --> A_ViewMap

    F_MarkMine --> A_ReviewCart
    A_ReviewCart --> A_AcceptTerms
    A_AcceptTerms --> F_ReqBooking

    F_ReqBooking --> B_ValidateBooking
    B_ValidateBooking --> D_InsertBooking
    D_InsertBooking --> F_ReqOrder

    F_ReqOrder --> B_CreateOrder
    B_CreateOrder --> G_GenOrder
    G_GenOrder --> D_InsertOrder
    D_InsertOrder --> F_LaunchRazorpay
    F_LaunchRazorpay --> A_PayModal

    A_PayModal --> G_AuthCard
    G_AuthCard --> F_DecidePayment
    
    F_DecidePayment -->|Success| G_ReturnSignature
    F_DecidePayment -->|Failed / Dismissed| F_ShowPaymentErr
    F_ShowPaymentErr --> A_ReviewCart

    G_ReturnSignature --> F_ReqVerify
    F_ReqVerify --> B_VerifyHMAC
    B_VerifyHMAC --> D_CommitPayment
    D_CommitPayment --> B_ConfirmBooking
    B_ConfirmBooking --> F_RedirectSuccess

    %% Parallel Fork for Delivery
    B_ConfirmBooking -->|Fork| B_TriggerTicket
    B_TriggerTicket --> T_GenQR
    T_GenQR --> T_RenderPDF
    T_RenderPDF --> D_InsertTicket
    D_InsertTicket --> T_SendMail

    F_RedirectSuccess --> A_ViewSuccess
    T_SendMail -->|Join| A_End
    A_ViewSuccess -->|Join| A_End
```

## 3. Workflow Observations & Lecture Concepts Applied
- **Swimlanes (Partitions):** Six swimlanes clearly assign responsibility for user actions, presentation, application logic, persistence, external financial processing, and notification delivery.
- **Decision vs. Merge:** Distinct decision diamonds are used for lock availability checks and payment authorization outcomes. Merge nodes cleanly recombine alternative paths (e.g., retrying checkout after a failed payment).
- **Fork and Join:** A synchronization fork occurs after booking confirmation: ticket generation and email dispatch proceed concurrently with client UI redirection, joining at workflow termination.
