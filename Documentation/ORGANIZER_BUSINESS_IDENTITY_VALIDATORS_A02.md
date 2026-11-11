# Sprint 2 Deliverable A-02: Organizer Business Identity Validators

**Project:** TicketFlow – Show Ticket Booking System  
**Sprint:** Sprint 2  
**Role:** Person A — Organizer and Business Verification  
**Deliverable:** A-02 (Organizer Business Identity Validators)  
**Status:** COMPLETE  

---

## 1. Executive Summary

Deliverable A-02 implements structural, algorithmic, and cross-consistency validation for business identity credentials submitted by event organizers on TicketFlow:
1. **Permanent Account Number (PAN)** structure and entity holder category verification.
2. **Goods and Services Tax Identification Number (GSTIN)** format, state code range, embedded PAN consistency, and official **GSTN Luhn Mod-36 checksum calculation**.
3. **Indian Financial System Code (IFSC)** banking format validation.
4. **Multi-field Coordinated Identity Validation** (`validate_organizer_identity`) ensuring cross-credential plausibility.
5. **Frontend Client Validators** (`identity-validators.ts`) providing immediate, responsive client-side feedback matching backend standards.

---

## 2. Compliance, Security, & Boundary Notice

Per the Admin Verification Shared Contract and sprint scope:
- **No External Government API Calls:** These validators perform offline syntactic, structural, and algorithmic checks. They do not invoke external government registries (NSDL, GSTN API) or certify document authenticity.
- **Privacy & Security Protection:** Raw sensitive values (full PAN, GSTIN, Bank Account numbers) are strictly excluded from exception messages, log output, and client-facing error payloads.
- **Standardized Disclaimer:** All validation results include a machine-readable compliance disclaimer:
  > *"Structural format validation confirms syntactical plausibility and mathematical checksums only. It does not certify government registration, active tax standing, or document authenticity."*

---

## 3. Detailed Specifications

### 3.1 PAN Validation & Business Type Matrix

The PAN is a 10-character alphanumeric identifier (`[A-Z]{5}[0-9]{4}[A-Z]`). The 4th character designates the legal entity type of the holder:

| BusinessType Enum | Allowed 4th Character | Holder Category |
| :--- | :--- | :--- |
| `INDIVIDUAL` | `P` | Person / Individual |
| `SOLE_PROPRIETOR` | `P` | Person / Individual |
| `COMPANY` | `C` | Company |
| `LLP` | `F` | Firm / Limited Liability Partnership |
| `TRUST` | `T`, `A` | Trust / Association of Persons |

Mismatches between the 4th character and the declared business type are rejected with code `BUSINESS_TYPE_MISMATCH`.

### 3.2 GSTIN Validation & Luhn Mod-36 Checksum

A GSTIN is a 15-character identifier with the structure:
- **Characters 1-2:** Valid 2-digit Indian State or Union Territory code (`01`–`38`, `97`, `99`).
- **Characters 3-12:** 10-character PAN of the entity.
- **Character 13:** Entity number of the same PAN within the state (`1`-`9`, `A`-`Z`).
- **Character 14:** Default character `Z`.
- **Character 15:** Mod-36 checksum digit computed over the first 14 characters.

#### Luhn Mod-36 Checksum Algorithm
GSTN uses a base-36 alphabet: `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ`.
Starting from index 0 with weight factor = 1, alternating 1 and 2:
```python
for char in gstin_14:
    code_point = GSTIN_CHAR_MAP[char]
    product = code_point * factor
    digit_sum = (product // 36) + (product % 36)
    total_sum += digit_sum
    factor = 1 if factor == 2 else 2

remainder = total_sum % 36
check_index = (36 - remainder) % 36
checksum = GSTIN_CHARSET[check_index]
```

### 3.3 IFSC Validation

The 11-character Indian Financial System Code adheres to RBI standards:
- **Characters 1-4:** 4 alphabetic characters representing the bank code (e.g., `HDFC`, `SBIN`, `ICIC`).
- **Character 5:** Strictly the numeric digit zero (`0`), reserved for future expansion.
- **Characters 6-11:** 6 alphanumeric characters representing the specific bank branch.

### 3.4 Multi-Field Cross-Validation

The coordinator function `validate_organizer_identity` verifies:
- PAN format and holder category match.
- GSTIN format, state code, and Mod-36 checksum.
- Embedded PAN in characters 3–12 matches the supplied external PAN (preventing accidental or fraudulent cross-entity credential mixing).
- IFSC bank code and branch format.

---

## 4. Verification Status Alignment

In synchronization with Section 2.3 of the *Admin Verification Shared Contract*, the `VerificationStatus` lifecycle includes:
- `DRAFT`: Applicant is drafting the verification request.
- `SUBMITTED`: Applicant has formally submitted the application for review.
- `IN_REVIEW`: Case is claimed and currently under evaluation by a reviewer.
- `PENDING`: Maintained for backward compatibility.
- `CHANGES_REQUESTED`: Reviewer has returned the submission for amendments.
- `APPROVED`: Organizer identity is verified and granted trust tier privileges.
- `REJECTED`: Application rejected with justification.
- `SUSPENDED`: Temporarily halted by platform admin or automated fraud flag.
- `EXPIRED`: Time-limited compliance license or documentation has elapsed.

The database migration `004_organizer_verification.sql` has been aligned to support all shared contract statuses in its `CHECK` constraint.

---

## 5. Test Suite & Verification Results

A comprehensive test suite of 58 automated unit tests was implemented in `sprint1_v2/backend/tests/test_identity_validators.py`.

Total backend test suite status:
```
======================= 84 passed, 10 warnings in 2.23s =======================
```
All existing tests (auth, contracts, security, migrations, fixtures) and all new identity validator tests pass with zero errors.
