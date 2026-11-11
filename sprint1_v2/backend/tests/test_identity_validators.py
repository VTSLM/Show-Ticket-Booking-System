"""
Unit Tests for Organizer Business Identity Validators.
Sprint 2 Deliverable A-02.

Covers:
1. PAN format and 4th-character holder category checks for all BusinessTypes.
2. Business-type mismatch scenarios.
3. GSTIN structure, state code, embedded PAN, and Mod-36 checksum verification.
4. GSTIN vs supplied PAN cross-matching consistency.
5. Tampered and invalid GSTIN checksum detection.
6. IFSC code validation (4-letter bank code, 5th-char zero, 6-char branch code).
7. Boundary, malformed, whitespace, and None input handling.
8. Multi-field coordinator validate_organizer_identity().
"""

import pytest
from models.verification import BusinessType
from services.identity_validators import (
    validate_pan,
    validate_gstin,
    validate_ifsc,
    calculate_gstin_checksum,
    validate_organizer_identity,
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


# ==============================================================================
# 2. GSTIN CHECKSUM & STRUCTURE TESTS
# ==============================================================================

def test_calculate_gstin_checksum_known_values():
    """Verify official GSTN Luhn Mod-36 checksum calculation against verified examples."""
    # 27 = Maharashtra, AAACT2727Q = TCS, 1 = first entity, Z = default -> checksum 'W'
    assert calculate_gstin_checksum("27AAACT2727Q1Z") == "W"

    # 27 = Maharashtra, AAPFU0939F = Firm, 1 = first entity, Z = default -> checksum 'V'
    assert calculate_gstin_checksum("27AAPFU0939F1Z") == "V"


def test_valid_gstin():
    """Verify that structurally valid GSTINs with correct checksums pass."""
    gstin = "27AAACT2727Q1ZW"
    res = validate_gstin(gstin)
    assert res.is_valid is True
    assert res.error_message is None


def test_valid_gstin_with_matching_pan():
    """Verify that a valid GSTIN matches its embedded PAN."""
    gstin = "27AAACT2727Q1ZW"
    matching_pan = "AAACT2727Q"
    res = validate_gstin(gstin, expected_pan=matching_pan)
    assert res.is_valid is True


def test_gstin_pan_mismatch():
    """Verify rejection when GSTIN's embedded PAN differs from supplied PAN."""
    gstin = "27AAACT2727Q1ZW"  # Embedded PAN is AAACT2727Q
    different_pan = "ABCPE1234F"
    res = validate_gstin(gstin, expected_pan=different_pan)
    assert res.is_valid is False
    assert res.error_code == "PAN_GSTIN_MISMATCH"
    assert "does not match the supplied PAN" in res.error_message


def test_invalid_gstin_checksum():
    """Verify detection of altered or tampered 15th checksum character."""
    # Correct is 'W', supply tampered 'X'
    tampered_gstin = "27AAACT2727Q1ZX"
    res = validate_gstin(tampered_gstin)
    assert res.is_valid is False
    assert res.error_code == "INVALID_CHECKSUM"
    assert "Expected checksum digit 'W'" in res.error_message


@pytest.mark.parametrize(
    "invalid_gstin,expected_code",
    [
        (None, "REQUIRED_FIELD"),
        ("", "REQUIRED_FIELD"),
        ("   ", "REQUIRED_FIELD"),
        ("27AAACT2727Q1Z", "INVALID_LENGTH"),
        ("27AAACT2727Q1ZW99", "INVALID_LENGTH"),
        ("999AACT2727Q1ZW", "INVALID_FORMAT"),   # 15 chars but digit at pos 2 breaks PAN pattern
        ("00AAACT2727Q1ZW", "INVALID_STATE_CODE"),     # 00 is not a valid state
        ("39AAACT2727Q1ZW", "INVALID_STATE_CODE"),     # State code out of range
        ("27123452727Q1ZW", "INVALID_FORMAT"),         # Missing PAN structure
        ("27AAACT2727Q1AW", "INVALID_FORMAT"),         # 14th char must be 'Z'
    ],
)
def test_invalid_gstin_structures(invalid_gstin, expected_code):
    """Verify rejection of malformed GSTINs (bad length, bad state code, bad format, bad checksum)."""
    res = validate_gstin(invalid_gstin)
    assert res.is_valid is False
    assert res.error_code == expected_code


# ==============================================================================
# 3. IFSC VALIDATION TESTS
# ==============================================================================

@pytest.mark.parametrize(
    "valid_ifsc",
    [
        "HDFC0001234",
        "SBIN0004321",
        "ICIC0000987",
        "KKBK0004567",
        "PUNB0123456",
        "BARB0BLRVAL",  # Alphanumeric branch code
    ],
)
def test_valid_ifsc_codes(valid_ifsc):
    """Verify valid 11-character Indian Financial System Codes."""
    res = validate_ifsc(valid_ifsc)
    assert res.is_valid is True
    assert res.error_message is None


def test_ifsc_case_and_whitespace():
    """Verify case normalization and trimming on IFSC codes."""
    res = validate_ifsc("  hdfc0001234  ")
    assert res.is_valid is True


@pytest.mark.parametrize(
    "invalid_ifsc,expected_code",
    [
        (None, "REQUIRED_FIELD"),
        ("", "REQUIRED_FIELD"),
        ("   ", "REQUIRED_FIELD"),
        ("HDFC001234", "INVALID_LENGTH"),         # 10 chars
        ("HDFC00001234", "INVALID_LENGTH"),       # 12 chars
        ("HDFC1001234", "INVALID_FIFTH_CHARACTER"),# 5th char is '1' instead of '0'
        ("HDFCA001234", "INVALID_FIFTH_CHARACTER"),# 5th char is 'A' instead of '0'
        ("12340001234", "INVALID_FORMAT"),        # First 4 must be letters
        ("HDFC000123!", "INVALID_FORMAT"),        # Special character
    ],
)
def test_invalid_ifsc_codes(invalid_ifsc, expected_code):
    """Verify rejection of invalid IFSC codes."""
    res = validate_ifsc(invalid_ifsc)
    assert res.is_valid is False
    assert res.error_code == expected_code


# ==============================================================================
# 4. MULTI-FIELD COORDINATED IDENTITY VALIDATION TESTS
# ==============================================================================

def test_validate_organizer_identity_all_valid():
    """Verify coordinated multi-field validation when all fields match."""
    results = validate_organizer_identity(
        pan="AAACT2727Q",
        business_type=BusinessType.COMPANY,
        gstin="27AAACT2727Q1ZW",
        ifsc="HDFC0001234",
    )
    assert results["pan"].is_valid is True
    assert results["gstin"].is_valid is True
    assert results["ifsc"].is_valid is True


def test_validate_organizer_identity_with_mismatch():
    """Verify coordinated validation detects mixed errors accurately."""
    results = validate_organizer_identity(
        pan="ABCPE1234F",                     # Individual PAN
        business_type=BusinessType.COMPANY,    # Mismatch with PAN!
        gstin="27AAACT2727Q1ZW",              # Mismatch with supplied PAN!
        ifsc="HDFC1001234",                   # 5th char not zero!
    )
    assert results["pan"].is_valid is False
    assert results["pan"].error_code == "BUSINESS_TYPE_MISMATCH"

    assert results["gstin"].is_valid is False
    # Since PAN was invalid, GSTIN does not cross-match against an invalid PAN
    # but GSTIN itself has valid checksum
    assert results["ifsc"].is_valid is False
    assert results["ifsc"].error_code == "INVALID_FIFTH_CHARACTER"


def test_disclaimer_included_on_all_results():
    """Verify compliance disclaimer is attached to validation result metadata."""
    res = validate_pan("ABCPE1234F")
    assert FORMAT_VALIDATION_DISCLAIMER in res.disclaimer
