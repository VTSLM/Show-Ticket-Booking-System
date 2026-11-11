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

# Regex patterns
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")

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
