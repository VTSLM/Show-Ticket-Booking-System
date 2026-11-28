# Class Diagram: Bookings, Payments, and Checkout

## 1. Description and Purpose
This diagram models the core financial and reservation transactions. It represents the lifecycle of a customer reservation from checkout creation through coupon discounts, payment order generation, Razorpay verification, and receipt issuance.

## 2. Class Diagram
```mermaid
classDiagram
    class Booking {
        +UUID id
        +String booking_number
        +UUID user_id
        +UUID show_id
        +Decimal total_amount
        +Decimal subtotal_amount
        +Decimal discount_amount
        +UUID coupon_id
        +String currency
        +BookingStatus status
        +DateTime booked_at
        +DateTime cancelled_at
        +String cancellation_reason
        +Decimal cancellation_charge
        +Decimal refund_amount
        +String refund_status
        +DateTime created_at
        +DateTime updated_at
        +isConfirmed() bool
        +isEligibleForCancellation() bool
    }

    class BookingSeat {
        +UUID id
        +UUID booking_id
        +UUID show_seat_id
        +Decimal unit_price
    }

    class BookingZone {
        +UUID id
        +UUID booking_id
        +UUID zone_id
        +Integer quantity
        +Decimal unit_price
    }

    class Coupon {
        +UUID id
        +UUID event_id
        +UUID created_by
        +String code
        +Decimal discount_percent
        +Boolean is_active
        +DateTime created_at
        +DateTime updated_at
        +calculateDiscount(Decimal amount) Decimal
    }

    class PaymentOrder {
        +UUID id
        +UUID booking_id
        +String razorpay_order_id
        +Decimal amount
        +String currency
        +String status
        +DateTime created_at
    }

    class Payment {
        +UUID id
        +UUID booking_id
        +String transaction_id
        +Decimal amount
        +String currency
        +PaymentMethod payment_method
        +PaymentStatus status
        +DateTime paid_at
        +DateTime created_at
    }

    class Receipt {
        +UUID id
        +String receipt_number
        +UUID payment_id
        +DateTime issued_at
        +String pdf_url
    }

    class ShowWaitlist {
        +UUID id
        +UUID show_id
        +UUID user_id
        +String status
        +DateTime created_at
    }

    class CancellationPolicy {
        +UUID id
        +String name
        +String description
        +Integer cutoff_hours
        +Decimal deduction_percentage
        +Decimal flat_cancellation_fee
        +Boolean is_refundable
        +Boolean is_default
        +DateTime created_at
    }

    class BookingStatus {
        <<enumeration>>
        pending
        confirmed
        cancelled
        expired
    }

    class PaymentStatus {
        <<enumeration>>
        created
        pending
        successful
        failed
        refunded
    }

    class PaymentMethod {
        <<enumeration>>
        razorpay
    }

    %% Relationships
    Booking "1" --> "1" BookingStatus : has status
    Booking "1" *-- "0..*" BookingSeat : reserves (cascade delete)
    Booking "1" *-- "0..*" BookingZone : reserves (cascade delete)
    Booking "0..*" o-- "0..1" Coupon : applies discount
    Booking "1" *-- "0..*" PaymentOrder : creates gateway orders
    Booking "1" *-- "0..*" Payment : records transactions
    Payment "1" --> "1" PaymentStatus : has status
    Payment "1" --> "1" PaymentMethod : processed by
    Payment "1" *-- "0..1" Receipt : generates upon success
    Booking "0..*" -- "0..1" CancellationPolicy : governed by
```

## 3. Structural Explanations & Ownership
- **`Booking *-- BookingSeat` & `Booking *-- BookingZone` (Composition `1` to `*`):** A booking seat or zone line item cannot exist without its parent booking (`ON DELETE CASCADE`). If a pending booking is purged, its reserved line items are removed.
- **`Booking o-- Coupon` (Aggregation `*` to `0..1`):** Coupons exist independently of bookings. A booking references an active coupon code to subtract `discount_amount` from `subtotal_amount`.
- **`Booking *-- Payment` (Composition `1` to `*`):** Payments are strictly tied to a single booking entity (`booking_id REFERENCES bookings(id) ON DELETE RESTRICT`). Multiple payment attempts may be created for a single booking if an initial attempt fails.
- **`Payment *-- Receipt` (Composition `1` to `0..1`):** A receipt is issued exactly once for a successful payment (`payment_id UUID NOT NULL UNIQUE REFERENCES payments(id)`).

## 4. Source Traceability
- Tables: `bookings`, `booking_seats`, `booking_zones`, `payment_orders`, `payments`, `receipts`, `coupons`, `show_waitlist`, `cancellation_policies`.
- Migrations: `0001_initial_schema.sql`, `0002_payment_gateway.sql`, `0003_tickets_receipts_and_birthdate.sql`, `0023_cancellation_and_refund_system.sql`, `0025_show_waitlist.sql`, `0027_booking_amounts.sql`, `0029_coupons.sql`.
- Backend Routers: `backend/routers/bookings.py`, `backend/routers/payments.py`.
