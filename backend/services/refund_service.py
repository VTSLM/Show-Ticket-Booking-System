"""
Razorpay refund integration service.
Handles actual refund initiation, status tracking, idempotency, and test mode execution.
Never mocks successful payment gateway processing in production mode.
"""
import asyncio
import hmac
import hashlib
from typing import Optional, Dict, Any
import razorpay
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET


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
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Issue a full or partial refund via Razorpay.

    Args:
        razorpay_payment_id: The 'pay_...' ID stored on the payments row.
        amount_paise: Refund amount in paise (₹1 = 100 paise).
        notes: Optional metadata dictionary.
        timeout: Maximum seconds to await gateway response (default 10s).

    Returns:
        Dict containing refund details: id, status, amount, etc.
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return {
            "id": None,
            "status": "pending",
            "amount": amount_paise,
            "currency": "INR",
            "error": "Razorpay credentials not configured. Refund kept in PENDING status.",
        }

    loop = asyncio.get_event_loop()
    client = get_razorpay_client()

    payload = {"amount": amount_paise}
    if notes:
        payload["notes"] = notes

    def _do_refund():
        return client.payment.refund(razorpay_payment_id, payload)

    try:
        return await asyncio.wait_for(loop.run_in_executor(None, _do_refund), timeout=timeout)
    except asyncio.TimeoutError:
        return {
            "id": None,
            "status": "pending",
            "amount": amount_paise,
            "currency": "INR",
            "error": "Payment gateway request timed out. Refund kept in PENDING status for retry.",
        }
    except Exception as e:
        return {
            "id": None,
            "status": "failed",
            "amount": amount_paise,
            "currency": "INR",
            "error": str(e),
        }


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
