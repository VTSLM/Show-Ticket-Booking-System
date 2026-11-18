"""
Razorpay refunds.

`initiate_razorpay_refund` makes the API call in a worker thread, with a timeout.
`refund_and_record` is what the cancel endpoint schedules as a background task:
it runs after the response has been sent, stores the rfnd_... id on the payment,
and never raises. A failure is logged for manual follow-up (the payment keeps an
empty `razorpay_refund_id`).
"""
import asyncio

import razorpay

from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from database import get_pool

# (connect, read) timeout in seconds for the Razorpay HTTP call
RAZORPAY_TIMEOUT = (5, 30)


async def initiate_razorpay_refund(razorpay_payment_id: str, amount_paise: int) -> str:
    """
    Issue a full or partial refund via Razorpay and return the refund id (rfnd_...).

    Raises:
        Exception: propagated from the Razorpay SDK or the HTTP timeout.
    """
    loop = asyncio.get_running_loop()
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

    def _do_refund():
        return client.payment.refund(
            razorpay_payment_id, {"amount": amount_paise}, timeout=RAZORPAY_TIMEOUT
        )

    result = await loop.run_in_executor(None, _do_refund)
    return result["id"]


async def refund_and_record(payment_id: str, razorpay_payment_id: str, amount_paise: int) -> None:
    """Background task: request the refund and store its id. Never raises."""
    try:
        refund_id = await initiate_razorpay_refund(razorpay_payment_id, amount_paise)
    except Exception as exc:
        print(f"[refund] Razorpay refund failed for payment {payment_id} (manual follow-up needed): {exc}")
        return

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE payments SET razorpay_refund_id = $1 WHERE id = $2",
                refund_id,
                payment_id,
            )
    except Exception as exc:
        print(f"[refund] refund {refund_id} succeeded but could not be saved for payment {payment_id}: {exc}")
