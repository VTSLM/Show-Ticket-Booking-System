"""
Unit Tests for Organizer Business Identity Validators.
Sprint 2 Deliverable A-02.

Covers:
1. PAN format and 4th-character holder category checks for all BusinessTypes.
2. Business-type mismatch scenarios.
3. Boundary, malformed, whitespace, and None input handling.
"""

import pytest
from models.verification import BusinessType
from services.identity_validators import (
    validate_pan,
    FORMAT_VALIDATION_DISCLAIMER,
)


# ==============================================================================
# 1. PAN VALIDATION TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "pan,business_type",
    [
        ("ABCPE1234F", BusinessType.INDIVIDUAL),       # 4th char 'P'
        ("ABCPD5678P", BusinessType.SOLE_PROPRIETOR),  # 4th char 'P'
        ("AAACC1122C", BusinessType.COMPANY),          # 4th char 'C'
        ("AAAFM3344L", BusinessType.LLP),              # 4th char 'F'
        ("AAATM7788T", BusinessType.TRUST),            # 4th char 'T'
        ("AAAAM9999M", BusinessType.TRUST),            # 4th char 'A' (AOP)
    ],
)
def test_valid_pan_for_each_business_type(pan, business_type):
    """Verify that structurally valid PANs with matching holder categories pass."""
    res = validate_pan(pan, business_type=business_type)
    assert res.is_valid is True
    assert res.error_message is None
    assert bool(res) is True


def test_pan_case_insensitivity_and_whitespace():
    """Verify that lowercase PANs and surrounding whitespace are safely cleaned."""
    res = validate_pan("  abcpe1234f  ", business_type=BusinessType.INDIVIDUAL)
    assert res.is_valid is True


def test_pan_without_business_type():
    """Verify that PAN structure alone is validated when business_type is omitted."""
    assert validate_pan("ABCPE1234F").is_valid is True
    assert validate_pan("AAACC1122C").is_valid is True


@pytest.mark.parametrize(
    "invalid_pan,expected_code",
    [
        (None, "REQUIRED_FIELD"),
        ("", "REQUIRED_FIELD"),
        ("   ", "REQUIRED_FIELD"),
        ("ABC12", "INVALID_LENGTH"),
        ("ABCPE12345F", "INVALID_LENGTH"),
        ("12CPE1234F", "INVALID_FORMAT"),
        ("ABCPE123AF", "INVALID_FORMAT"),
        ("ABCPE12345", "INVALID_FORMAT"),
        ("ABCPE-1234", "INVALID_FORMAT"),
        ("ABCPE!234F", "INVALID_FORMAT"),
    ],
)
def test_invalid_pan_structures(invalid_pan, expected_code):
    """Verify rejection of malformed or invalid PAN structures."""
    res = validate_pan(invalid_pan)
    assert res.is_valid is False
    assert res.error_code == expected_code
    assert res.error_message is not None
    # Ensure raw sensitive value is not leaked into the error message
    if invalid_pan:
        assert invalid_pan not in res.error_message


@pytest.mark.parametrize(
    "pan,declared_type,expected_char",
    [
        ("ABCPE1234F", BusinessType.COMPANY, "P"),   # Individual PAN for Company
        ("AAACC1122C", BusinessType.INDIVIDUAL, "C"),# Company PAN for Individual
        ("AAACC1122C", BusinessType.LLP, "C"),       # Company PAN for LLP
        ("AAAFM3344L", BusinessType.TRUST, "F"),     # Firm PAN for Trust
        ("AAATM7788T", BusinessType.COMPANY, "T"),   # Trust PAN for Company
    ],
)
def test_pan_business_type_mismatch(pan, declared_type, expected_char):
    """Verify that mismatch between 4th character and declared business type is rejected."""
    res = validate_pan(pan, business_type=declared_type)
    assert res.is_valid is False
    assert res.error_code == "BUSINESS_TYPE_MISMATCH"
    assert f"'{expected_char}'" in res.error_message
    assert declared_type.value in res.error_message


def test_pan_invalid_business_type_string():
    """Verify handling when an unsupported business type is passed as string."""
    res = validate_pan("ABCPE1234F", business_type="UNREGISTERED_CLUB")
    assert res.is_valid is False
    assert res.error_code == "INVALID_BUSINESS_TYPE"
