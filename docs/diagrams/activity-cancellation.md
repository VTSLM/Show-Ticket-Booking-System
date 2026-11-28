# Activity Diagram: Booking Cancellation and Refund Process

## 1. Description and Purpose
This activity diagram models the end-to-end business and technical workflow for customer booking cancellation, eligibility assessment, deduction fee calculation, transactional seat release, payment gateway refund processing, and notification dispatch.

## 2. Activity Diagram with Swimlanes
```mermaid
flowchart TD
    %% Swimlanes
    subgraph Lane_Customer["Customer (Actor)"]
        C_Start((Start))
        C_ClickCancel["Click 'Cancel Booking' on /bookings/{id}"]
        C_ReviewTerms["Review Cancellation Terms & Deduction Fee"]
        C_ConfirmCancel["Submit Cancellation Reason"]
        C_ViewSuccess["View Refund Status in Tracker"]
        C_End((End))
    end

    subgraph Lane_Frontend["Next.js Frontend"]
        F_ReqElig["GET /api/cancellations/{id}/cancel-eligibility"]
        F_DecideElig{Eligible?}
        F_ShowModal["Render CancelConfirmationModal"]
        F_ShowIneligible["Display Ineligible Warning Tooltip"]
        F_ReqCancel["POST /api/cancellations/{id}/cancel"]
        F_UpdateUI["Show Cancellation Confirmed & Progress Tracker"]
    end

    subgraph Lane_Backend["FastAPI Backend (cancellations.py & refund_service.py)"]
        B_EvalPolicy["Evaluate Policy: Hours to show vs Cutoff"]
        B_BeginTx["Begin Database Transaction"]
        B_CommitCancel["Mark Booking 'cancelled' & Tickets 'cancelled'"]
        B_ReleaseSeats["Reset show_seats to 'available' & clear locks"]
        B_QueueRefund["Insert Refund record with status 'PENDING'"]
        B_CommitTx["Commit Database Transaction"]
        B_TriggerGateway["Dispatch Asynchronous Razorpay Refund Call"]
    end

    subgraph Lane_DB["PostgreSQL Database"]
        D_ReadBooking["SELECT booking, show, policy, payments"]
        D_UpdateBooking["UPDATE bookings SET status='cancelled', refund_status='PENDING'"]
        D_ResetSeats["UPDATE show_seats SET status='available'"]
        D_InsertRefund["INSERT INTO refunds"]
        D_UpdateRefund["UPDATE refunds SET status='PROCESSED'"]
    end

    subgraph Lane_Gateway["Razorpay Payment Gateway"]
        G_ProcessRefund["Execute Gateway Refund API Call"]
        G_DecideGateway{Gateway<br/>Success?}
        G_ReturnSuccess["Return 200 OK (Refund ID)"]
        G_ReturnError["Return Error / Timeout"]
    end

    subgraph Lane_Notification["Notification Subsystem"]
        N_SendEmail["Dispatch Refund Email via Gmail SMTP"]
        N_CreateInApp["INSERT INTO notifications"]
    end

    %% Flow Connections
    C_Start --> C_ClickCancel
    C_ClickCancel --> F_ReqElig
    F_ReqElig --> B_EvalPolicy
    B_EvalPolicy --> D_ReadBooking
    D_ReadBooking --> B_EvalPolicy

    B_EvalPolicy --> F_DecideElig
    F_DecideElig -->|No: Past Cutoff| F_ShowIneligible
    F_ShowIneligible --> C_End
    F_DecideElig -->|Yes: Within Window| F_ShowModal

    F_ShowModal --> C_ReviewTerms
    C_ReviewTerms --> C_ConfirmCancel
    C_ConfirmCancel --> F_ReqCancel

    F_ReqCancel --> B_BeginTx
    B_BeginTx --> B_CommitCancel
    B_CommitCancel --> D_UpdateBooking
    D_UpdateBooking --> B_ReleaseSeats
    B_ReleaseSeats --> D_ResetSeats
    D_ResetSeats --> B_QueueRefund
    B_QueueRefund --> D_InsertRefund
    D_InsertRefund --> B_CommitTx

    B_CommitTx --> F_UpdateUI
    F_UpdateUI --> C_ViewSuccess

    B_CommitTx --> B_TriggerGateway
    B_TriggerGateway --> G_ProcessRefund
    G_ProcessRefund --> G_DecideGateway

    G_DecideGateway -->|Success| G_ReturnSuccess
    G_ReturnSuccess --> D_UpdateRefund
    D_UpdateRefund --> N_SendEmail
    D_UpdateRefund --> N_CreateInApp
    N_SendEmail --> C_End
    N_CreateInApp --> C_End

    G_DecideGateway -->|Failed| G_ReturnError
    G_ReturnError --> B_MarkFailed["UPDATE refunds SET status='FAILED', retry_count++"]
    B_MarkFailed --> C_End
```

## 3. Key Design Observations
- **Asymmetric Coupling:** Seat inventory recovery does not wait for banking settlement. The seats are immediately released within the database transaction (`B_ReleaseSeats`), ensuring venue capacity is promptly restored even if the gateway refund operation requires asynchronous retries.
- **Fail-Safe Administrative Retries:** A failed refund transition (`G_ReturnError`) logs the failure for administrative queue intervention (`/api/cancellations/admin/refunds/{id}/retry`) rather than rolling back the entire seat cancellation.
