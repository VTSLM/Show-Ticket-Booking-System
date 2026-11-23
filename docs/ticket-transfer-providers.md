# Ticket transfer providers

Transfers entered by mobile number still go to an existing TicketFlow account.
Email invites are available for people without a TicketFlow account. Recipients can also see transfer updates in the notification bell.

## Demo reimbursement through Razorpay Payment Gateway

The sender can select **Request their share (test payment)** when they send
numbered seats or standing tickets to a friend. Send a separate transfer to
each friend to split the booking. The recipient sees the test amount on
Received tickets and can pay and accept, or decline.
This option uses the existing Razorpay Payment Gateway test keys and can be
disabled with `TRANSFER_DEMO_PAYMENTS=false`. Live keys are refused. Transfers sent without a payment request are free.

The demo price is the transferred items' share of the original captured
amount, rounded down to paise. That accounts for discounts and allocates
booking-level charges proportionally. The checkout displays the test amount
before payment. For a transfer to be eligible, the original booking payment
must also be captured in the configured Razorpay test account. Enable automatic
payment capture in Razorpay Test Mode so the demo can confirm the friend’s charge.

The app checks the recorded order with Razorpay before issuing the ticket.
It then simulates a partial refund to the original booking payment. If the
transfer is no longer available when the test charge is confirmed, TicketFlow
refunds the recipient's test payment instead. The recipient can check the
status from Received tickets, and the sender can see the original booking's
test refund status under the transfer. A background check also recovers
payments after a tab closes or a request is interrupted.

For a demo, apply local migrations through `0036`, book with a test card, transfer part of the
booking to a second account with **Request their share** selected, then pay and
accept in that account. Verify the original booking's refund and the separate recipient
charge in the Razorpay Test Mode dashboard.
