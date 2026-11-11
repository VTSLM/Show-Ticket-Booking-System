"""
Organizer Business Identity Validators — Sprint 2.
Person A: A-02 Deliverable.

Implements structural, algorithmic, and cross-consistency validation for:
1. PAN (Permanent Account Number) structure and holder-category matching.
2. GSTIN (Goods and Services Tax Identification Number) structure, embedded PAN,
   and official Luhn Mod-36 checksum verification.
3. IFSC (Indian Financial System Code) banking structure verification.
4. Coordinated cross-field plausibility verification (PAN vs GSTIN consistency).

IMPORTANT SECURITY & COMPLIANCE NOTICE:
Structural format validation verifies syntactical validity, checksums, and plausibility.
It does NOT query external government registries or prove legal existence / document authenticity.
Raw sensitive inputs (PAN, GSTIN, Bank Accounts) are NEVER logged or echoed in error text.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Union
from models.verification import BusinessType

# Disclaimer metadata
FORMAT_VALIDATION_DISCLAIMER = (
    "Structural format validation confirms syntactical plausibility and mathematical checksums only. "
    "It does not certify government registration, active tax standing, or document authenticity."
)

# Base-36 alphabet mapping used by GSTN for Luhn Mod-36 checksum calculation
GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_CHAR_MAP = {c: i for i, c in enumerate(GSTIN_CHARSET)}

# Valid 2-digit Indian State/UT Codes under GSTN
VALID_GST_STATE_CODES = {
    f"{i:02d}" for i in range(1, 39)
}.union({"97", "99"})  # 97=Other Territory, 99=Centre Jurisdiction / Non-resident

# Regex patterns
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

# Mapping of BusinessType to allowed 4th character holder codes in Indian PAN:
# - 'P' = Individual / Person (used by INDIVIDUAL and SOLE_PROPRIETOR)
# - 'C' = Company
# - 'F' = Firm / Limited Liability Partnership (LLP)
# - 'T' = Trust (or 'A' = Association of Persons for some charitable trusts)
BUSINESS_TYPE_PAN_HOLDER_MAP: Dict[BusinessType, Set[str]] = {
    BusinessType.INDIVIDUAL: {"P"},
    BusinessType.SOLE_PROPRIETOR: {"P"},
    BusinessType.COMPANY: {"C"},
    BusinessType.LLP: {"F"},
    BusinessType.TRUST: {"T", "A"},
}


@dataclass
class ValidationResult:
    """Standardized result returned by identity format validators."""
    is_valid: bool
    error_message: Optional[str] = None
    field: Optional[str] = None
    error_code: Optional[str] = None
    disclaimer: str = FORMAT_VALIDATION_DISCLAIMER

    def __bool__(self) -> bool:
        return self.is_valid


def _resolve_business_type(b_type: Union[BusinessType, str]) -> Optional[BusinessType]:
    """Safely cast string or BusinessType into enum instance."""
    if isinstance(b_type, BusinessType):
        return b_type
    if isinstance(b_type, str):
        normalized = b_type.strip().upper()
        try:
            return BusinessType(normalized)
        except ValueError:
            return None
    return None


def calculate_gstin_checksum(gstin_14: str) -> str:
    """
    Calculate the 15th checksum character of a 14-character GSTIN prefix
    using the official GSTN Luhn Mod-36 algorithm.
    """
    if not isinstance(gstin_14, str) or len(gstin_14) != 14:
        raise ValueError("Input to calculate_gstin_checksum must be exactly 14 characters")

    cleaned = gstin_14.strip().upper()
    factor = 1
    total_sum = 0
    mod = 36

    for char in cleaned:
        code_point = GSTIN_CHAR_MAP.get(char)
        if code_point is None:
            raise ValueError(f"Invalid character in GSTIN prefix: '{char}'")
        
        product = code_point * factor
        digit_sum = (product // mod) + (product % mod)
        total_sum += digit_sum
        
        factor = 1 if factor == 2 else 2

    remainder = total_sum % mod
    check_index = (mod - remainder) % mod
    return GSTIN_CHARSET[check_index]


def validate_pan(
    pan: Optional[str],
    business_type: Optional[Union[BusinessType, str]] = None,
) -> ValidationResult:
    """
    Validate an Indian Permanent Account Number (PAN).
    
    Checks:
    1. Mandatory value present and non-empty.
    2. Format: Exactly 10 characters with structure [A-Z]{5}[0-9]{4}[A-Z].
    3. Fourth character entity category matches declared BusinessType (if provided).
    
    Security note: The raw PAN value is never echoed in error messages.
    """
    if pan is None or not str(pan).strip():
        return ValidationResult(
            is_valid=False,
            error_message="PAN is required",
            field="pan",
            error_code="REQUIRED_FIELD",
        )

    cleaned = str(pan).strip().upper()

    if len(cleaned) != 10:
        return ValidationResult(
            is_valid=False,
            error_message="PAN must be exactly 10 alphanumeric characters",
            field="pan",
            error_code="INVALID_LENGTH",
        )

    if not PAN_REGEX.match(cleaned):
        return ValidationResult(
            is_valid=False,
            error_message="Invalid PAN format. Must be 5 letters, 4 digits, and 1 letter (e.g. ABCDE1234F)",
            field="pan",
            error_code="INVALID_FORMAT",
        )

    # Holder category validation against business type
    if business_type is not None:
        resolved_type = _resolve_business_type(business_type)
        if resolved_type is None:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported business type: '{business_type}'",
                field="business_type",
                error_code="INVALID_BUSINESS_TYPE",
            )

        fourth_char = cleaned[3]
        allowed_holders = BUSINESS_TYPE_PAN_HOLDER_MAP.get(resolved_type, set())

        if fourth_char not in allowed_holders:
            holder_desc = {
                "P": "Individual ('P')",
                "C": "Company ('C')",
                "F": "Partnership / LLP ('F')",
                "T": "Trust ('T')",
                "A": "Association of Persons ('A')",
            }
            allowed_names = " or ".join(holder_desc.get(h, f"'{h}'") for h in sorted(allowed_holders))
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"PAN category character '{fourth_char}' does not match declared business type '{resolved_type.value}'. "
                    f"Expected category code: {allowed_names}."
                ),
                field="pan",
                error_code="BUSINESS_TYPE_MISMATCH",
            )

    return ValidationResult(is_valid=True)


def validate_gstin(
    gstin: Optional[str],
    expected_pan: Optional[str] = None,
) -> ValidationResult:
    """
    Validate an Indian Goods and Services Tax Identification Number (GSTIN).
    
    Checks:
    1. Format: Exactly 15 characters, conforming to ^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$.
    2. Valid Indian State / UT 2-digit code.
    3. Characters 3-12 form a syntactically valid embedded PAN.
    4. Characters 3-12 match supplied expected_pan (if provided).
    5. Official GSTN Luhn Mod-36 checksum verification on the 15th character.
    
    Security note: Raw GSTIN is never echoed in error messages.
    """
    if gstin is None or not str(gstin).strip():
        return ValidationResult(
            is_valid=False,
            error_message="GSTIN is required",
            field="gstin",
            error_code="REQUIRED_FIELD",
        )

    cleaned = str(gstin).strip().upper()

    if len(cleaned) != 15:
        return ValidationResult(
            is_valid=False,
            error_message="GSTIN must be exactly 15 characters long",
            field="gstin",
            error_code="INVALID_LENGTH",
        )

    if not GSTIN_REGEX.match(cleaned):
        return ValidationResult(
            is_valid=False,
            error_message="Invalid GSTIN structure. Expected 2 state digits, 10-character PAN, 1 entity code, 'Z', and 1 checksum digit",
            field="gstin",
            error_code="INVALID_FORMAT",
        )

    # State code validation
    state_code = cleaned[:2]
    if state_code not in VALID_GST_STATE_CODES:
        return ValidationResult(
            is_valid=False,
            error_message=f"Invalid state code '{state_code}' in GSTIN. Must be a valid Indian State/UT code (01-38, 97, 99)",
            field="gstin",
            error_code="INVALID_STATE_CODE",
        )

    # Embedded PAN check
    embedded_pan = cleaned[2:12]
    embedded_pan_res = validate_pan(embedded_pan)
    if not embedded_pan_res.is_valid:
        return ValidationResult(
            is_valid=False,
            error_message="The PAN embedded within the GSTIN is structurally invalid",
            field="gstin",
            error_code="INVALID_EMBEDDED_PAN",
        )

    # Consistency with external PAN
    if expected_pan is not None and str(expected_pan).strip():
        clean_expected = str(expected_pan).strip().upper()
        if embedded_pan != clean_expected:
            return ValidationResult(
                is_valid=False,
                error_message="The PAN embedded in the GSTIN does not match the supplied PAN",
                field="gstin",
                error_code="PAN_GSTIN_MISMATCH",
            )

    # Checksum validation using official GSTN Mod-36
    try:
        calculated_check = calculate_gstin_checksum(cleaned[:14])
    except Exception:
        return ValidationResult(
            is_valid=False,
            error_message="Failed to compute GSTIN checksum",
            field="gstin",
            error_code="CHECKSUM_COMPUTATION_ERROR",
        )

    actual_check = cleaned[14]
    if actual_check != calculated_check:
        return ValidationResult(
            is_valid=False,
            error_message=f"Invalid GSTIN checksum digit '{actual_check}'. Expected checksum digit '{calculated_check}'",
            field="gstin",
            error_code="INVALID_CHECKSUM",
        )

    return ValidationResult(is_valid=True)


def validate_ifsc(ifsc: Optional[str]) -> ValidationResult:
    """
    Validate an Indian Financial System Code (IFSC).
    
    Checks:
    1. Mandatory value present.
    2. Format: Exactly 11 characters.
    3. Structure: 4 alphabetic bank code letters, strictly '0' at index 4 (5th char),
       followed by 6 alphanumeric branch code characters.
       
    Security note: Raw IFSC input is never echoed into error responses.
    """
    if ifsc is None or not str(ifsc).strip():
        return ValidationResult(
            is_valid=False,
            error_message="IFSC code is required",
            field="ifsc",
            error_code="REQUIRED_FIELD",
        )

    cleaned = str(ifsc).strip().upper()

    if len(cleaned) != 11:
        return ValidationResult(
            is_valid=False,
            error_message="IFSC code must be exactly 11 characters long",
            field="ifsc",
            error_code="INVALID_LENGTH",
        )

    if cleaned[4] != "0":
        return ValidationResult(
            is_valid=False,
            error_message="Invalid IFSC: 5th character must strictly be the digit zero ('0')",
            field="ifsc",
            error_code="INVALID_FIFTH_CHARACTER",
        )

    if not IFSC_REGEX.match(cleaned):
        return ValidationResult(
            is_valid=False,
            error_message="Invalid IFSC format. Must be 4 letters, digit '0', and 6 alphanumeric characters (e.g. HDFC0001234)",
            field="ifsc",
            error_code="INVALID_FORMAT",
        )

    return ValidationResult(is_valid=True)
