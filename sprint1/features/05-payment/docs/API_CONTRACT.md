# Feature 05 shared API contract

Shared mode uses FastAPI + Supabase/PostgreSQL and requires `Authorization: Bearer <Firebase ID token>` on booking, order, verification, recheck and receipt routes. The API validates the token and looks up the internal user from `users.firebase_uid`. The browser never supplies an authoritative total or internal user ID.

## Load booking

`GET /api/payments/booking/{booking_id}`

Returns a persisted booking only when it belongs to the authenticated user. The response includes `booking_id`, `booking_number`, `event_title`, venue/screen/city, show date, selected seats, count, persisted total and `seat_locks_valid`. The shared schema only stores `bookings.total_amount`, so the frontend shows one booking total instead of fabricating tax/convenience-fee line items.

## Create order

`POST /api/payments/orders`

```json
{"booking_id":"<canonical pending booking UUID>"}
```

The backend locks the booking row, confirms ownership and pending status, verifies every selected `show_seat` lock is still held by that user, and reads the amount/currency from `bookings`. It creates the order server-side with Razorpay Test Mode. If the booking already has an unresolved or review-required order, the endpoint responds with `409` and names the existing order so the client can reconcile it. Live keys are rejected.

## Verify checkout

`POST /api/payments/orders/{order_id}/verify`

```json
{
  "razorpay_order_id":"order_...",
  "razorpay_payment_id":"pay_...",
  "razorpay_signature":"<signature returned by Razorpay Checkout>"
}
```

The API checks that the path order matches the payload, verifies Razorpay's checkout signature, fetches the provider payment record, checks order/amount/currency, and persists provider state. The booking and seats are confirmed only after provider status `captured` and valid owned locks are verified in a database transaction.

## Reconcile an existing order

`POST /api/payments/orders/{order_id}/recheck`

```json
{"payment_id":"pay_..."}
```

The payment ID may be omitted when Checkout closed before returning one. The API queries Razorpay attempts for that exact order. Only when the attempt collection is empty and the provider order independently reports `attempts=0`, `amount_paid=0`, and `status=created` may the order be marked cancelled/unpaid. Provider/network uncertainty remains `verification_pending`. This endpoint never creates an order or charge.

## Result semantics

The result exposes `order_id`, `payment.payment_id`, amount, currency, method, status, payment timestamp when available, receipt, `booking_confirmation_status`, and `sandbox: true` / `live_payment: false`. The UI displays provider timestamps as IST. `successful_needs_review` means Razorpay captured the payment, but the booking's seat locks could not be confirmed; do not pay again. The booking team must reconcile the order and determine the correct refund/seat resolution.

## Status source of truth

A browser success callback is not proof of a captured payment. Razorpay's server-fetched payment state is authoritative. This implementation uses synchronous reads; add signed webhooks with replay/idempotency protections and monitoring before production use. Keep the Razorpay Key Secret, Firebase Admin credentials and database URL on the server only.
