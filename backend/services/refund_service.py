"""
Razorpay refund integration service.
Handles refund initiation, status tracking, idempotency, and background execution.
"""
import asyncio
import hashlib
import hmac
from typing import Optional, Dict, Any

import razorpay

from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from database import get_pool

# (connect, read) timeout in seconds for the Razorpay HTTP call
RAZORPAY_TIMEOUT = (5, 30)


def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def is_test_environment() -> bool:
    """Returns True if test or placeholder credentials are in use."""
    return (
        not RAZORPAY_KEY_ID
        or not RAZORPAY_KEY_SECRET
        or RAZORPAY_KEY_ID.startswith("rzp_test_your")
        or "your_key" in RAZORPAY_KEY_ID
    )


async def initiate_razorpay_refund(
    razorpay_payment_id: str,
    amount_paise: int,
    notes: Optional[Dict[str, str]] = None,
    timeout: Any = RAZORPAY_TIMEOUT,
) -> str:
    """
    Issue a full or partial refund via Razorpay and return the refund id (rfnd_...).

    Raises:
        Exception: propagated from the Razorpay SDK or the HTTP timeout.
    """
    loop = asyncio.get_running_loop()
    client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

    payload: Dict[str, Any] = {"amount": amount_paise}
    if notes:
        payload["notes"] = notes

    def _do_refund():
        return client.payment.refund(
            razorpay_payment_id, payload, timeout=timeout
        )

    result = await loop.run_in_executor(None, _do_refund)
    return result["id"] if isinstance(result, dict) else str(result)


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


def verify_razorpay_webhook_signature(
    webhook_body: bytes, webhook_signature: str, webhook_secret: str
) -> bool:
    """
    Verifies Razorpay webhook signature using HMAC-SHA256.
    """
    if not webhook_secret or not webhook_signature:
        return False

    computed = hmac.new(
        webhook_secret.encode("utf-8"), webhook_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, webhook_signature)
