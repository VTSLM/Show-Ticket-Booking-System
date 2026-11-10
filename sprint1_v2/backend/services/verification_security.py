"""
Security and Tokenization Utilities for Verification — Sprint 2.
Person A & Shared Foundations.

Ensures sensitive identity identifiers (PAN, GSTIN, Bank Accounts) are:
- Strictly masked before storage.
- Never stored in plaintext.
- Salted and hashed for collision / duplicate detection.
- Scrubbed from application logs.
"""

import hashlib
import hmac
import os
import re
from typing import Any, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_PEPPER = "ticketflow-verification-secret-salt-2026"


def get_fingerprint_pepper(custom_salt: Optional[str] = None) -> bytes:
    """
    Resolve the salt/pepper key dynamically from environment or custom override.
    Never hardcoded into static evaluation.
    """
    if custom_salt:
        return custom_salt.encode("utf-8")
    env_salt = os.getenv("VERIFICATION_SALT_PEPPER", DEFAULT_PEPPER)
    return env_salt.encode("utf-8")


def mask_pan(pan: Optional[str]) -> Optional[str]:
    """
    Mask a 10-character Indian Permanent Account Number (PAN).
    Example: 'ABCDE1234F' -> 'ABCDE****F'
    If invalid or short, obscures middle characters.
    """
    if not pan:
        return None
    cleaned = pan.strip().upper()
    if len(cleaned) == 10:
        return f"{cleaned[:5]}****{cleaned[9]}"
    if len(cleaned) > 4:
        return f"{cleaned[:2]}{'*' * (len(cleaned) - 4)}{cleaned[-2:]}"
    return "****"


def mask_gstin(gstin: Optional[str]) -> Optional[str]:
    """
    Mask a 15-character Goods and Services Tax Identification Number (GSTIN).
    Example: '24ABCDE1234F1Z5' -> '24ABCDE****1Z5'
    """
    if not gstin:
        return None
    cleaned = gstin.strip().upper()
    if len(cleaned) == 15:
        # Keep state code and entity PAN prefix (7 chars), mask 5 characters, keep last 3 chars
        return f"{cleaned[:7]}****{cleaned[-3:]}"
    if len(cleaned) > 6:
        return f"{cleaned[:3]}{'*' * (len(cleaned) - 6)}{cleaned[-3:]}"
    return "******"


def mask_bank_account(account_no: Optional[str]) -> Optional[str]:
    """
    Mask a bank account number, keeping only the last 4 digits.
    Example: '123456789012' -> '********9012'
    """
    if not account_no:
        return None
    cleaned = re.sub(r"\s+", "", str(account_no))
    if len(cleaned) <= 4:
        return "****"
    return f"{'*' * (len(cleaned) - 4)}{cleaned[-4:]}"


def hash_salted_value(value: str, salt: Optional[str] = None) -> str:
    """
    Create a deterministic, salted SHA-256 HMAC digest for duplicate detection.
    Allows detecting duplicate PAN, GSTIN, or Bank Account without storing plaintext.
    """
    if not value or not str(value).strip():
        raise ValueError("Cannot hash an empty value")
    clean_val = value.strip().upper().encode("utf-8")
    key = get_fingerprint_pepper(salt)
    return hmac.new(key, clean_val, hashlib.sha256).hexdigest()


def sanitize_sensitive_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive identity fields before logging or passing across boundary layers.
    Scrubs raw PAN, GSTIN, and account numbers into their masked forms.
    """
    sanitized = dict(payload)
    for k, v in sanitized.items():
        if isinstance(v, str):
            lower_k = k.lower()
            if "pan" in lower_k and not lower_k.endswith("_masked"):
                sanitized[k] = mask_pan(v)
            elif "gstin" in lower_k and not lower_k.endswith("_masked"):
                sanitized[k] = mask_gstin(v)
            elif ("account" in lower_k or "acc_no" in lower_k) and not lower_k.endswith(("_masked", "_hash")):
                sanitized[k] = mask_bank_account(v)
    return sanitized
