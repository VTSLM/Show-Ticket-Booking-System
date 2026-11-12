"""
Razorpay refund — fire-and-forget helper.
Runs the blocking SDK call in a thread executor so it never blocks the event loop.
"""
import asyncio
import razorpay
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET


async def initiate_razorpay_refund(razorpay_payment_id: str, amount_paise: int) -> str:
    """
    Issue a full or partial refund via Razorpay.

    Args:
        razorpay_payment_id: The 'pay_...' ID stored on the payments row.
        amount_paise: Refund amount in paise (₹1 = 100 paise).

    Returns:
        The Razorpay refund ID (rfnd_...).

    Raises:
        Exception: Propagated from the Razorpay SDK on failure.
    """
    loop = asyncio.get_event_loop()
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

    def _do_refund():
        return client.payment.refund(razorpay_payment_id, {"amount": amount_paise})

    result = await loop.run_in_executor(None, _do_refund)
    return result["id"]
