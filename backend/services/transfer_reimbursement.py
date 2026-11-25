"""Run a RazorpayX reimbursement smoke test with a preconfigured test beneficiary."""

import argparse
import json
import os
import re
from uuid import UUID

import httpx

PAYOUT_URL = "https://api.razorpay.com/v1/payouts"


class PayoutTestError(Exception):
    """The test payout could not be verified."""


def run_test_payout(reference: UUID, amount: int, payout_id: str | None = None) -> dict:
    """Create an idempotent test payout, or check an existing payout against its intent."""
    key = os.getenv("RAZORPAYX_TEST_KEY_ID", "")
    secret = os.getenv("RAZORPAYX_TEST_KEY_SECRET", "")
    account = os.getenv("RAZORPAYX_TEST_ACCOUNT_NUMBER", "")
    beneficiary = os.getenv("RAZORPAYX_TEST_FUND_ACCOUNT_ID", "")
    if not re.fullmatch(r"rzp_test_[A-Za-z0-9]+", key) or not secret:
        raise PayoutTestError("Set RazorpayX test-mode credentials.")
    if not re.fullmatch(r"[0-9]+", account) or not re.fullmatch(r"fa_[A-Za-z0-9]+", beneficiary):
        raise PayoutTestError("Set a test account number and a test bank fund account ID.")
    if amount < 100:
        raise PayoutTestError("Enter an amount of at least 100 paise.")
    if payout_id and not re.fullmatch(r"pout_[A-Za-z0-9]+", payout_id):
        raise PayoutTestError("Enter a valid payout ID.")

    expected = {
        "fund_account_id": beneficiary,
        "amount": amount,
        "currency": "INR",
        "reference_id": str(reference),
    }
    try:
        with httpx.Client(auth=(key, secret), timeout=10) as client:
            if payout_id:
                response = client.get(f"{PAYOUT_URL}/{payout_id}")
            else:
                response = client.post(
                    PAYOUT_URL,
                    headers={"X-Payout-Idempotency": str(reference)},
                    json={
                        **expected,
                        "account_number": account,
                        "mode": "IMPS",
                        "purpose": "payout",
                        "queue_if_low_balance": False,
                    },
                )
            response.raise_for_status()
            payout = response.json()
    except httpx.HTTPStatusError as exc:
        raise PayoutTestError(f"RazorpayX returned HTTP {exc.response.status_code}.") from None
    except (httpx.RequestError, ValueError):
        raise PayoutTestError(
            "Could not confirm the payout response. Retry with the same reference and amount."
        ) from None

    if not isinstance(payout, dict) or any(payout.get(k) != v for k, v in expected.items()):
        raise PayoutTestError("RazorpayX returned a payout that does not match the test intent.")
    actual_id = payout.get("id")
    status = payout.get("status")
    if (not isinstance(actual_id, str) or not re.fullmatch(r"pout_[A-Za-z0-9]+", actual_id)
            or (payout_id and actual_id != payout_id) or not isinstance(status, str) or not status):
        raise PayoutTestError("RazorpayX returned an invalid payout ID or status.")
    return {"test_mode": True, "payout_id": actual_id, "provider_status": status}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=UUID, required=True, help="UUID to reuse for this payout")
    parser.add_argument("--amount-paise", type=int, required=True)
    parser.add_argument("--payout-id", help="Check this previously created payout instead of creating one")
    args = parser.parse_args()
    try:
        print(json.dumps(run_test_payout(args.reference, args.amount_paise, args.payout_id)))
    except PayoutTestError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
