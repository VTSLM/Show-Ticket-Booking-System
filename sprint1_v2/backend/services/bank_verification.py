"""
Mock Bank Verification Adapter — Sprint 2: Deliverable A-05.
Person A: Organizer Verification & Compliance.

Provides a pluggable mock bank account verification adapter.
Simulates penny-drop / account validation without executing real banking API calls.
Can be cleanly swapped with a real payment/banking provider (e.g., Razorpay Fund Account Validation).
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional
from services.identity_validators import validate_ifsc

BANK_VERIFICATION_DISCLAIMER = (
    "MOCK VERIFICATION ADAPTER — This is an administrative simulation for testing and compliance. "
    "No live bank transfer, penny drop, or government API call was executed."
)

# Known IFSC prefix mappings for realistic mock responses
IFSC_BANK_MAPPINGS = {
    "SBIN": "State Bank of India",
    "HDFC": "HDFC Bank Ltd",
    "ICIC": "ICICI Bank Ltd",
    "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda",
    "AXIS": "Axis Bank Ltd",
    "KKBK": "Kotak Mahindra Bank Ltd",
    "UTIB": "Axis Bank Ltd",
    "CNRB": "Canara Bank",
    "IDIB": "Indian Bank",
}


def verify_mock_bank_account(
    holder_name: str,
    ifsc: str,
    account_number: Optional[str] = None,
    account_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simulates penny-drop bank account validation.
    
    Returns structured result:
    - verified: bool
    - status: "VERIFIED" | "NAME_MISMATCH" | "INVALID_IFSC" | "FAILED"
    - bank_name: str
    - registered_name: str
    - account_holder_matched: bool
    - reference_id: str
    - disclaimer: str
    - timestamp: str
    """
    clean_holder = (holder_name or "").strip()
    clean_ifsc = (ifsc or "").strip().upper()
    clean_acc = (account_number or "").strip()

    # 1. Validate IFSC format
    ifsc_val = validate_ifsc(clean_ifsc)
    if not ifsc_val.is_valid:
        return {
            "verified": False,
            "status": "INVALID_IFSC",
            "bank_name": "Unknown Bank",
            "registered_name": "",
            "account_holder_matched": False,
            "reference_id": f"mock_err_{int(datetime.now(timezone.utc).timestamp())}",
            "error_message": ifsc_val.error_message,
            "disclaimer": BANK_VERIFICATION_DISCLAIMER,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Derive bank name from IFSC
    bank_code = clean_ifsc[:4]
    bank_name = IFSC_BANK_MAPPINGS.get(bank_code, f"{bank_code} Banking Corporation")

    # 2. Simulated failure trigger: account ending in 0000 or 'fail'
    if clean_acc.endswith("0000") or "fail" in clean_holder.lower():
        return {
            "verified": False,
            "status": "FAILED",
            "bank_name": bank_name,
            "registered_name": "",
            "account_holder_matched": False,
            "reference_id": f"mock_fail_{int(datetime.now(timezone.utc).timestamp())}",
            "error_message": "Account invalid, blocked, or inactive at destination bank.",
            "disclaimer": BANK_VERIFICATION_DISCLAIMER,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # 3. Simulated name mismatch trigger: holder name containing 'mismatch'
    if "mismatch" in clean_holder.lower():
        return {
            "verified": False,
            "status": "NAME_MISMATCH",
            "bank_name": bank_name,
            "registered_name": f"{clean_holder.upper()} HOLDINGS UNMATCHED",
            "account_holder_matched": False,
            "reference_id": f"mock_nm_{int(datetime.now(timezone.utc).timestamp())}",
            "error_message": "Account holder name did not match bank record name.",
            "disclaimer": BANK_VERIFICATION_DISCLAIMER,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # 4. Successful simulated verification
    return {
        "verified": True,
        "status": "VERIFIED",
        "bank_name": bank_name,
        "registered_name": clean_holder.upper(),
        "account_holder_matched": True,
        "reference_id": f"mock_utr_{int(datetime.now(timezone.utc).timestamp())}",
        "error_message": None,
        "disclaimer": BANK_VERIFICATION_DISCLAIMER,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

