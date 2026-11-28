# System Architecture Diagram

## 1. Description and Purpose
This diagram illustrates the high-level system architecture of the TicketFlow platform. TicketFlow is built as a distributed, service-oriented web application employing a four-tier deployment style (Presentation Client, Presentation Server, Application Logic Server, and Relational Database) augmented with third-party cloud services.

## 2. Diagram
```mermaid
flowchart TD
    subgraph ClientTier["Client Tier (User Equipment)"]
        Browser["User Web Browser\n(Desktop / Mobile)"]
    end

    subgraph PresentationTier["Presentation Tier (Vercel / Node.js)"]
        NextJS["Next.js 14 App Router\n(React 18, TypeScript, TailwindCSS)\n- app/ shows, bookings, admin, manager\n- contexts/ AuthContext, LocationContext\n- lib/api.ts, transfersApi.ts, etc."]
    end

    subgraph ApplicationTier["Application Tier (Azure App Service / Linux Container)"]
        FastAPI["FastAPI 0.164 Backend (Python 3.12, Uvicorn)\n- Middleware: CORS, Path ID Validator\n- Dependencies: get_current_user, require_role\n- Routers: browse, seats, bookings, payments, transfers, etc.\n- Services: dynamic_pricing, ticket_service, refund_service, etc."]
        WebSocketMgr["WebSocket Connection Manager\n(Active client connections by show_id)"]
        BGTasks["Background Async Tasks\n- _cleanup_expired_locks()\n- _listen_seat_events() (pg_notify)"]
    end

    subgraph DataTier["Data Tier (Managed PostgreSQL 16)"]
        Postgres[("PostgreSQL 16 Database\n- 54 Tables (users, shows, bookings, etc.)\n- Row Level Security (RLS) policies\n- LISTEN / NOTIFY 'seat_events' channel\n- Raw asyncpg connection pool (max 20)")]
    end

    subgraph ExternalServices["External Cloud Integrations"]
        FirebaseAuth["Firebase Authentication\n(Identity Management, JWT token issuance)"]
        SupabaseStorage["Supabase Storage\n(Document Vault, Avatars, Event Posters)"]
        Razorpay["Razorpay Payment Gateway\n(Orders API, Signatures, Refund API, Webhooks)"]
        GmailSMTP["Gmail SMTP Relay\n(Booking confirmations, PDF tickets, Transfer invites)"]
        OpenAI["OpenAI API\n(Chatbot Assistant & Review Summarization)"]
    end

    %% Client to Presentation & Application
    Browser -->|"HTTP / HTTPS (HTML, JS, CSS)"| NextJS
    Browser -->|"REST API (JSON over HTTPS)"| FastAPI
    Browser -->|"WebSocket (wss://)"| WebSocketMgr
    Browser -->|"Direct Auth Flow (Email/Password, Google)"| FirebaseAuth

    %% Next.js SSR / API calls
    NextJS -.->|"Server-side rendering API calls"| FastAPI

    %% Backend to Database
    FastAPI -->|"asyncpg connection pool (SQL queries)"| Postgres
    WebSocketMgr -->|"Broadcast triggers"| Postgres
    BGTasks -->|"Periodic lock release & LISTEN loop"| Postgres

    %% Backend to External Services
    FastAPI -->|"Verify ID Token (Firebase Admin SDK)"| FirebaseAuth
    FastAPI -->|"Upload / Signed URLs (REST API)"| SupabaseStorage
    FastAPI -->|"Create Orders & Issue Refunds (HTTPS)"| Razorpay
    Razorpay -.->|"Payment / Refund Webhook"| FastAPI
    FastAPI -->|"Send Emails (aiosmtplib / smtplib)"| GmailSMTP
    FastAPI -->|"Completions / Chat stream"| OpenAI
```

## 3. Architectural Interpretation
- **Client & Presentation Separation:** The frontend is decoupled into client-side React components running in the user's browser and Next.js server-rendered pages. Authentication is initiated on the client via Firebase Authentication SDK, while API calls carry Firebase JWT ID tokens to FastAPI.
- **Stateless Application Layer:** FastAPI instances maintain minimal in-memory state (only active WebSocket connections for connected users). All durable state resides in PostgreSQL.
- **Cross-Instance Synchronization:** When seats are locked or released, the instance handling the HTTP request broadcasts to local WebSockets and dispatches a PostgreSQL `pg_notify('seat_events', payload)`. Remote instances pick up the notification via a background listener task, enabling horizontal scalability without requiring Redis.
- **Open Layering:** The API router handlers invoke both business logic services and parameterised asyncpg SQL directly on the pooled database connection, prioritizing low latency and raw query efficiency.

## 4. Implementation References
- `backend/main.py`: Lifespan hooks, router wiring, CORS middleware, background tasks.
- `backend/database.py`: `get_pool()`, `get_conn()`, connection pool configuration.
- `backend/dependencies.py`: `get_current_user()`, `require_role()`.
- `backend/routers/seats.py`: `ConnectionManager`, WebSocket endpoint, pg_notify broadcast.
- `frontend/lib/api.ts`: Centralized fetch client handling bearer tokens and session expiry.
