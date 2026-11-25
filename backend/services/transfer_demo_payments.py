"""Razorpay Payment Gateway checkout and original-payment refunds for demo transfers."""

import logging
import os
import re

import asyncpg
import httpx

from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from services import ticket_transfer as transfers

logger = logging.getLogger(__name__)
BASE_URL = "https://api.razorpay.com/v1/"


def enabled() -> bool:
    return (
        os.getenv("TRANSFER_DEMO_PAYMENTS", "true").lower() == "true"
        and RAZORPAY_KEY_ID.startswith("rzp_test_")
        and bool(RAZORPAY_KEY_SECRET)
    )


async def gateway(method: str, path: str, **kwargs) -> dict:
    if not enabled():
        raise transfers.TransferError(404, "Demo payment is unavailable")
    try:
        async with httpx.AsyncClient(base_url=BASE_URL,
                                     auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET), timeout=8) as client:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
    except (httpx.HTTPError, ValueError):
        pass
    raise transfers.TransferError(502, "Razorpay Test Mode could not confirm the request. Try again shortly.")


def payment_id_valid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"pay_[A-Za-z0-9]+", value) is not None


async def open_checkout(conn: asyncpg.Connection, transfer_id: str, user_id: str) -> dict:
    if not enabled():
        raise transfers.TransferError(404, "Demo payment is unavailable")

    async with conn.transaction():
        tr = await transfers._load_for_update(conn, transfer_id)
        if not tr or str(tr["to_user_id"]) != user_id:
            raise transfers.TransferError(404, "Transfer not found")
        if not tr.get("requested_share_paise"):
            raise transfers.TransferError(409, "The sender did not request a test payment")
        if (tr["status"] != "pending" or tr["ticket_used"] or tr["ticket_status"] in ("cancelled", "used")
                or tr["booking_status"] != "confirmed"):
            raise transfers.TransferError(409, "This transfer is no longer available")
        if not await conn.fetchval(
            """SELECT tt.created_at + interval '24 hours' > clock_timestamp()
                      AND s.start_time > clock_timestamp()
               FROM ticket_transfers tt JOIN bookings b ON b.id = tt.booking_id
               JOIN shows s ON s.id = b.show_id WHERE tt.id = $1::uuid""", transfer_id,
        ):
            raise transfers.TransferError(409, "This transfer has expired")

        existing = await conn.fetchrow(
            "SELECT * FROM transfer_demo_payments WHERE transfer_id = $1::uuid", transfer_id,
        )
        if existing:
            order_id, amount = existing["razorpay_order_id"], existing["amount_paise"]
        else:
            quote = await transfers.quote_demo_share(conn, transfer_id)
            original_id = quote["transaction_id"]
            amount = int(quote["amount"])
            if amount != tr["requested_share_paise"]:
                raise transfers.TransferError(409, "The booking amount changed. Ask the sender for a new transfer.")
            original = await gateway("GET", f"payments/{original_id}")
            if (original.get("id") != original_id or original.get("status") != "captured"
                    or original.get("currency") != "INR" or original.get("amount") != quote["captured_paise"]
                    or not isinstance(original.get("amount_refunded"), int)
                    or amount > original["amount"] - original["amount_refunded"]):
                raise transfers.TransferError(409, "The original test payment cannot cover this refund")
            order = await gateway("POST", "orders", json={
                "amount": amount, "currency": "INR", "receipt": f"tr_{transfer_id}",
            })
            order_id = order.get("id")
            if (not isinstance(order_id, str) or not re.fullmatch(r"order_[A-Za-z0-9]+", order_id)
                    or order.get("amount") != amount or order.get("currency") != "INR"):
                raise transfers.TransferError(502, "Razorpay returned an invalid test order")
            await conn.execute(
                """INSERT INTO transfer_demo_payments (transfer_id, razorpay_order_id, original_payment_id, amount_paise)
                   VALUES ($1::uuid, $2, $3, $4)""", transfer_id, order_id, original_id, amount,
            )
    return {"order_id": order_id, "amount": amount, "currency": "INR", "key_id": RAZORPAY_KEY_ID}


async def reconcile(conn: asyncpg.Connection, row: dict) -> str:
    transfer_id = str(row["transfer_id"])
    if not row["recipient_payment_id"]:
        payments = await gateway("GET", f"orders/{row['razorpay_order_id']}/payments")
        matched = next((p for p in payments.get("items", []) if (
            payment_id_valid(p.get("id")) and p.get("order_id") == row["razorpay_order_id"]
            and p.get("status") == "captured" and p.get("currency") == "INR"
            and p.get("amount") == row["amount_paise"]
        )), None)
        if not matched:
            return "awaiting_payment"

        async with conn.transaction():
            tr = await transfers._load_for_update(conn, transfer_id)
            row = await conn.fetchrow(
                "SELECT * FROM transfer_demo_payments WHERE transfer_id = $1::uuid", transfer_id,
            )
            if not row["recipient_payment_id"]:
                try:
                    await transfers.respond_to_transfer(
                        conn, str(tr["to_user_id"]), transfer_id, accept=True, paid_checkout=True,
                    )
                    target = "buyer"
                    await transfers._notify_transfer(conn, str(tr["from_user_id"]), "transfer.payment_received", {
                        "transfer_id": transfer_id, "booking_id": str(tr["booking_id"]),
                        "event_title": tr["event_title"], "recipient_name": tr["recipient_name"],
                        "amount_paise": row["amount_paise"],
                    })
                except transfers.TransferError as exc:
                    if exc.status_code not in (400, 404, 409):
                        raise
                    # A scan, cancellation or expiry won. Return the test charge
                    # to the friend without issuing a ticket.
                    target = "recipient"
                    await transfers._notify_transfer(conn, str(tr["to_user_id"]), "transfer.payment_returned", {
                        "transfer_id": transfer_id, "event_title": tr["event_title"],
                        "amount_paise": row["amount_paise"],
                    })
                row = await conn.fetchrow(
                    """UPDATE transfer_demo_payments SET recipient_payment_id = $2, refund_target = $3,
                              refund_status = 'pending' WHERE transfer_id = $1::uuid RETURNING *""",
                    transfer_id, matched["id"], target,
                )

    if row["refund_status"] in ("processed", "failed"):
        return f"{row['refund_target']}_refund_{row['refund_status']}"

    payment_id = row["original_payment_id"] if row["refund_target"] == "buyer" else row["recipient_payment_id"]
    path = f"payments/{payment_id}/refund"
    if row["refund_id"]:
        refund = await gateway("GET", f"payments/{payment_id}/refunds/{row['refund_id']}")
    else:
        refund = await gateway(
            "POST", path, headers={"X-Refund-Idempotency": f"ticketflow-{transfer_id}"},
            json={
                "amount": row["amount_paise"],
                "speed": "normal",
                "receipt": f"tr_{transfer_id}",
                "notes": {"ticketflow_demo_transfer_id": transfer_id},
            },
        )
    refund_id = refund.get("id")
    status = refund.get("status")
    if (refund.get("payment_id") != payment_id or refund.get("amount") != row["amount_paise"]
            or refund.get("currency") != "INR" or not isinstance(refund_id, str)
            or not re.fullmatch(r"rfnd_[A-Za-z0-9]+", refund_id)
            or (row["refund_id"] and row["refund_id"] != refund_id)
            or status not in ("pending", "processed", "failed")):
        raise transfers.TransferError(502, "Razorpay returned an unverified refund")
    await conn.execute(
        """UPDATE transfer_demo_payments SET refund_id = $2, refund_status = $3
           WHERE transfer_id = $1::uuid AND refund_status = 'pending'""",
        transfer_id, refund_id, status,
    )
    return f"{row['refund_target']}_refund_{status}"


async def reconcile_pending(conn: asyncpg.Connection) -> None:
    if not enabled():
        return
    rows = await conn.fetch(
        """SELECT * FROM transfer_demo_payments
           WHERE (refund_status IS NULL OR refund_status = 'pending')
             AND checked_at < now() - interval '30 seconds'
           ORDER BY checked_at LIMIT 10"""
    )
    for row in rows:
        transfer_id = str(row["transfer_id"])
        await conn.execute("UPDATE transfer_demo_payments SET checked_at = now() WHERE transfer_id = $1::uuid",
                           transfer_id)
        try:
            await reconcile(conn, row)
        except transfers.TransferError:
            logger.warning("Demo payment reconciliation will retry for transfer %s", transfer_id)
