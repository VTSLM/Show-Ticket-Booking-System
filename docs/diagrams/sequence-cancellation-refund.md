# Sequence Diagram: Booking Cancellation and Refund Flow

## 1. Description and Purpose
This sequence diagram models the booking cancellation and refund process. It details the customer cancellation request, policy cutoff validation, deduction fee calculation, Razorpay refund processing, automatic seat release, and email notification.

## 2. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Browser)
    participant NextJS as Next.js Frontend
    participant CancelCtrl as cancellations.py (API)
    participant PolicySvc as cancellation_policy_service.py
    participant RefundSvc as refund_service.py
    participant NotifySvc as cancellation_notification_service.py
    participant DB as PostgreSQL 16
    participant Razorpay as Razorpay API
    participant SMTP as Gmail SMTP Server

    %% Eligibility Check
    Customer ->> NextJS: Clicks "Cancel Booking" on /bookings/{id}
    NextJS ->> CancelCtrl: GET /api/cancellations/{booking_id}/cancel-eligibility
    CancelCtrl ->> DB: Fetch booking, show start_time, payment records, and policy
    CancelCtrl ->> PolicySvc: evaluate_eligibility(booking, show_time, policy)
    
    alt Hours to Show < Cutoff Hours (e.g. 2 hours before show)
        PolicySvc -->> CancelCtrl: Ineligible: cutoff window expired
        CancelCtrl -->> NextJS: 200 OK {is_eligible: false, reason: "Cutoff passed"}
        NextJS -->> Customer: Disable cancellation button with explanatory tooltip
    else Eligible for Cancellation
        PolicySvc -->> CancelCtrl: Eligible (refund_amount, deduction_amount, fee)
        CancelCtrl -->> NextJS: 200 OK {is_eligible: true, refund_amount: 540.00, fee: 60.00}
        NextJS -->> Customer: Display CancelConfirmationModal with refund breakdown
    end

    %% Execution of Cancellation
    Customer ->> NextJS: Confirm Cancellation (Enter Reason)
    NextJS ->> CancelCtrl: POST /api/cancellations/{booking_id}/cancel {reason: "Personal emergency"}
    
    CancelCtrl ->> DB: BEGIN TRANSACTION
    CancelCtrl ->> DB: Re-verify booking status = 'confirmed' AND eligibility
    CancelCtrl ->> DB: UPDATE bookings SET status='cancelled', cancelled_at=NOW(), cancellation_reason=$reason, refund_amount=$amt, refund_status='PENDING'
    CancelCtrl ->> DB: UPDATE show_seats SET status='available', locked_by=NULL, locked_until=NULL WHERE id IN (booking_seats)
    CancelCtrl ->> DB: UPDATE tickets SET status='cancelled' WHERE booking_id=$booking_id
    CancelCtrl ->> DB: INSERT INTO refunds (booking_id, payment_id, amount, status='PENDING')
    CancelCtrl ->> DB: COMMIT TRANSACTION

    CancelCtrl ->> RefundSvc: process_refund_async(refund_id)
    RefundSvc ->> Razorpay: POST /v1/payments/{payment_id}/refund {amount: 54000}
    
    alt Razorpay Refund Successful
        Razorpay -->> RefundSvc: 200 OK {id: "rfnd_abc123", status: "processed"}
        RefundSvc ->> DB: UPDATE refunds SET status='PROCESSED', razorpay_refund_id='rfnd_abc123'
        RefundSvc ->> DB: UPDATE bookings SET refund_status='PROCESSED'
        RefundSvc ->> NotifySvc: send_cancellation_notifications(booking_id)
        NotifySvc ->> DB: INSERT INTO notifications (type='booking_cancelled')
        NotifySvc ->> SMTP: Send cancellation & refund receipt email
        SMTP -->> Customer: Delivery of refund confirmation email
    else Razorpay Gateway Error / Network Failure
        Razorpay -->> RefundSvc: Error / Timeout
        RefundSvc ->> DB: UPDATE refunds SET status='FAILED', retry_count=retry_count+1
        RefundSvc ->> DB: UPDATE bookings SET refund_status='FAILED'
        Note over RefundSvc: Admin can retry failed refunds via /api/cancellations/admin/refunds/{id}/retry
    end

    CancelCtrl -->> NextJS: 200 OK {status: "cancelled", refund_amount: 540.00}
    NextJS -->> Customer: Show Cancellation Confirmed banner & RefundProgressTracker
```

## 3. Important Implementation Notes
- **Transactional Seat Release:** Cancellation marks the booking cancelled and simultaneously resets the associated `show_seats` records back to `available` within a single database transaction, ensuring the seats immediately become available for other customers to reserve.
- **Refund Failure Fault-Tolerance:** If the Razorpay refund API fails (e.g., due to bank gateway downtime), the booking cancellation remains valid and the refund record is marked `FAILED` for administrative retry, preventing customer seats from remaining occupied.
