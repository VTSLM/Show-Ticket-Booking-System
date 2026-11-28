# Component Diagram

## 1. Description and Purpose
Following UML Component Diagram conventions (Lecture 25, Object Design), this diagram depicts how runtime deployable components in TicketFlow are wired together through provided and required interfaces.

## 2. Component Diagram
```mermaid
flowchart LR
    subgraph ClientComponent["Client-Side Runtime"]
        SPA["«component»\nNext.js SPA\n(React Client Bundle)"]
    end

    subgraph ServerComponents["Application Runtime (Host Container)"]
        API["«component»\nFastAPI Application Server\n(Uvicorn ASGI Engine)"]
        WS["«component»\nWebSocket Hub\n(ConnectionManager)"]
        BGWorker["«component»\nBackground Tasks\n(Lock Cleanup & Event Listener)"]
    end

    subgraph DataComponents["Persistence Runtime"]
        PostgresDB["«component»\nPostgreSQL 16 Engine\n(Relational Storage & Pub/Sub)"]
    end

    subgraph CloudComponents["Third-Party Cloud Services"]
        FirebaseAuth["«component»\nFirebase Auth Service"]
        StorageService["«component»\nSupabase Storage"]
        PaymentGateway["«component»\nRazorpay Gateway"]
        SMTPRelay["«component»\nGmail SMTP Server"]
        AIService["«component»\nOpenAI Platform"]
    end

    %% Interfaces
    I_HTTP["( ) I_RestAPI\n(HTTPS / JSON)"]
    I_WS["( ) I_WebSocket\n(WSS JSON)"]
    I_Auth["( ) I_FirebaseAuth\n(OAuth2 / OIDC)"]
    I_SQL["( ) I_PostgreSQL\n(asyncpg protocol)"]
    I_PubSub["( ) I_PgNotify\n(LISTEN/NOTIFY)"]
    I_S3["( ) I_Storage\n(S3-compatible REST)"]
    I_Pay["( ) I_Payment\n(Razorpay REST API)"]
    I_Mail["( ) I_MailRelay\n(SMTP TLS)"]
    I_AI["( ) I_LLM\n(OpenAI REST)"]

    %% Wiring
    API --- I_HTTP
    SPA --> I_HTTP

    WS --- I_WS
    SPA --> I_WS

    FirebaseAuth --- I_Auth
    SPA --> I_Auth
    API --> I_Auth

    PostgresDB --- I_SQL
    API --> I_SQL
    BGWorker --> I_SQL

    PostgresDB --- I_PubSub
    API --> I_PubSub
    BGWorker --> I_PubSub
    BGWorker -.->|"Relays remote events"| WS

    StorageService --- I_S3
    API --> I_S3

    PaymentGateway --- I_Pay
    API --> I_Pay
    PaymentGateway -.->|"Webhook callback"| API

    SMTPRelay --- I_Mail
    API --> I_Mail

    AIService --- I_AI
    API --> I_AI
```

## 3. Detailed Component View: Booking & Payment Subsystem
```mermaid
flowchart TD
    subgraph Client["Web Browser"]
        SeatUI["Seat Selection UI\n(VenueLayoutCanvas)"]
        CheckoutUI["Checkout & Payment Form"]
    end

    subgraph BackendAPI["FastAPI Backend Container"]
        SeatController["Seats Router\n(/api/seats/*)"]
        BookingController["Bookings Router\n(/api/bookings/*)"]
        PaymentController["Payments Router\n(/api/payments/*)"]
        TicketGenerator["Ticket Service\n(PDF & QR Builder)"]
    end

    subgraph Database["PostgreSQL 16"]
        SeatsTable[("show_seats\nshow_zones")]
        BookingsTable[("bookings\nbooking_seats")]
        PaymentsTable[("payment_orders\npayments")]
        TicketsTable[("tickets")]
    end

    subgraph External["External Processors"]
        RazorpayAPI["Razorpay Payment Gateway"]
        MailService["SMTP Mail Dispatcher"]
    end

    SeatUI -->|"POST /lock"| SeatController
    SeatController -->|"UPDATE ... WHERE status='available'"| SeatsTable
    
    CheckoutUI -->|"POST /api/bookings"| BookingController
    BookingController -->|"INSERT INTO bookings"| BookingsTable

    CheckoutUI -->|"POST /api/payments/orders"| PaymentController
    PaymentController -->|"Create Order"| RazorpayAPI
    PaymentController -->|"INSERT INTO payment_orders"| PaymentsTable

    RazorpayAPI -.->|"HMAC Signature"| CheckoutUI
    CheckoutUI -->|"POST /orders/{id}/verify"| PaymentController
    
    PaymentController -->|"INSERT INTO payments"| PaymentsTable
    PaymentController -->|"UPDATE status='confirmed'"| BookingsTable
    PaymentController -->|"Trigger ticket creation"| TicketGenerator

    TicketGenerator -->|"INSERT INTO tickets"| TicketsTable
    TicketGenerator -->|"Send PDF Ticket"| MailService
```

## 4. Component Port & Interface Specifications
- **`I_RestAPI`**: RESTful interface providing JSON request/response contracts for show discovery, seat locking, booking, payment, and transfers.
- **`I_WebSocket`**: Bidirectional persistent channel pushing real-time seat lock (`{"type": "lock", "seat_ids": [...]}`) and release events to connected viewers of a show.
- **`I_PgNotify`**: Internal pub/sub connector via PostgreSQL `LISTEN/NOTIFY ('seat_events')` used to coordinate multiple backend container replicas.
