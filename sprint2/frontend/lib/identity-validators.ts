/**
 * Organizer Business Identity Validators — Frontend Client Library.
 * Sprint 2 Deliverable A-02.
 *
 * Implements client-side structural validation for PAN, GSTIN, and IFSC codes.
 * Mirrors backend rules defined in services/identity_validators.py.
 */

import { BusinessType } from "./verification-types";

export const FORMAT_VALIDATION_DISCLAIMER =
  "Structural format validation confirms syntactical plausibility and mathematical checksums only. " +
  "It does not certify government registration, active tax standing, or document authenticity.";

const GSTIN_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
const IFSC_REGEX = /^[A-Z]{4}0[A-Z0-9]{6}$/;

const BUSINESS_TYPE_PAN_HOLDER_MAP: Record<BusinessType, string[]> = {
  INDIVIDUAL: ["P"],
  SOLE_PROPRIETOR: ["P"],
  COMPANY: ["C"],
  LLP: ["F"],
  TRUST: ["T", "A"],
};

export interface ClientValidationResult {
  isValid: boolean;
  errorMessage?: string;
  field?: string;
  errorCode?: string;
  disclaimer: string;
}

export function calculateGstinChecksum(gstin14: string): string {
  if (!gstin14 || gstin14.length !== 14) {
    throw new Error("Input must be exactly 14 characters");
  }

  const cleaned = gstin14.toUpperCase();
  let factor = 1;
  let totalSum = 0;
  const mod = 36;

  for (let i = 0; i < cleaned.length; i++) {
    const codePoint = GSTIN_CHARSET.indexOf(cleaned[i]);
    if (codePoint < 0) {
      throw new Error(`Invalid character in GSTIN prefix: '${cleaned[i]}'`);
    }

    const product = codePoint * factor;
    const digitSum = Math.floor(product / mod) + (product % mod);
    totalSum += digitSum;

    factor = factor === 2 ? 1 : 2;
  }

  const remainder = totalSum % mod;
  const checkIndex = (mod - remainder) % mod;
  return GSTIN_CHARSET[checkIndex];
}

export function validatePan(
  pan?: string | null,
  businessType?: BusinessType | null
): ClientValidationResult {
  if (!pan || !pan.trim()) {
    return {
      isValid: false,
      errorMessage: "PAN is required",
      field: "pan",
      errorCode: "REQUIRED_FIELD",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  const cleaned = pan.trim().toUpperCase();

  if (cleaned.length !== 10) {
    return {
      isValid: false,
      errorMessage: "PAN must be exactly 10 alphanumeric characters",
      field: "pan",
      errorCode: "INVALID_LENGTH",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  if (!PAN_REGEX.test(cleaned)) {
    return {
      isValid: false,
      errorMessage:
        "Invalid PAN format. Must be 5 letters, 4 digits, and 1 letter (e.g. ABCDE1234F)",
      field: "pan",
      errorCode: "INVALID_FORMAT",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  if (businessType) {
    const fourthChar = cleaned[3];
    const allowed = BUSINESS_TYPE_PAN_HOLDER_MAP[businessType] || [];
    if (!allowed.includes(fourthChar)) {
      return {
        isValid: false,
        errorMessage: `PAN category character '${fourthChar}' does not match declared business type '${businessType}'`,
        field: "pan",
        errorCode: "BUSINESS_TYPE_MISMATCH",
        disclaimer: FORMAT_VALIDATION_DISCLAIMER,
      };
    }
  }

  return { isValid: true, disclaimer: FORMAT_VALIDATION_DISCLAIMER };
}

export function validateGstin(
  gstin?: string | null,
  expectedPan?: string | null
): ClientValidationResult {
  if (!gstin || !gstin.trim()) {
    return {
      isValid: false,
      errorMessage: "GSTIN is required",
      field: "gstin",
      errorCode: "REQUIRED_FIELD",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  const cleaned = gstin.trim().toUpperCase();

  if (cleaned.length !== 15) {
    return {
      isValid: false,
      errorMessage: "GSTIN must be exactly 15 characters long",
      field: "gstin",
      errorCode: "INVALID_LENGTH",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  if (!GSTIN_REGEX.test(cleaned)) {
    return {
      isValid: false,
      errorMessage:
        "Invalid GSTIN structure. Expected 2 state digits, 10-character PAN, 1 entity code, 'Z', and 1 checksum digit",
      field: "gstin",
      errorCode: "INVALID_FORMAT",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  const embeddedPan = cleaned.slice(2, 12);
  const panCheck = validatePan(embeddedPan);
  if (!panCheck.isValid) {
    return {
      isValid: false,
      errorMessage: "The PAN embedded within the GSTIN is structurally invalid",
      field: "gstin",
      errorCode: "INVALID_EMBEDDED_PAN",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  if (expectedPan && expectedPan.trim()) {
    if (embeddedPan !== expectedPan.trim().toUpperCase()) {
      return {
        isValid: false,
        errorMessage:
          "The PAN embedded in the GSTIN does not match the supplied PAN",
        field: "gstin",
        errorCode: "PAN_GSTIN_MISMATCH",
        disclaimer: FORMAT_VALIDATION_DISCLAIMER,
      };
    }
  }

  try {
    const expectedChecksum = calculateGstinChecksum(cleaned.slice(0, 14));
    if (cleaned[14] !== expectedChecksum) {
      return {
        isValid: false,
        errorMessage: `Invalid GSTIN checksum digit '${cleaned[14]}'. Expected '${expectedChecksum}'`,
        field: "gstin",
        errorCode: "INVALID_CHECKSUM",
        disclaimer: FORMAT_VALIDATION_DISCLAIMER,
      };
    }
  } catch {
    return {
      isValid: false,
      errorMessage: "Failed to compute GSTIN checksum",
      field: "gstin",
      errorCode: "CHECKSUM_COMPUTATION_ERROR",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  return { isValid: true, disclaimer: FORMAT_VALIDATION_DISCLAIMER };
}

export function validateIfsc(ifsc?: string | null): ClientValidationResult {
  if (!ifsc || !ifsc.trim()) {
    return {
      isValid: false,
      errorMessage: "IFSC code is required",
      field: "ifsc",
      errorCode: "REQUIRED_FIELD",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  const cleaned = ifsc.trim().toUpperCase();

  if (cleaned.length !== 11) {
    return {
      isValid: false,
      errorMessage: "IFSC code must be exactly 11 characters long",
      field: "ifsc",
      errorCode: "INVALID_LENGTH",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  if (cleaned[4] !== "0") {
    return {
      isValid: false,
      errorMessage:
        "Invalid IFSC: 5th character must strictly be the digit zero ('0')",
      field: "ifsc",
      errorCode: "INVALID_FIFTH_CHARACTER",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  if (!IFSC_REGEX.test(cleaned)) {
    return {
      isValid: false,
      errorMessage:
        "Invalid IFSC format. Must be 4 letters, digit '0', and 6 alphanumeric characters (e.g. HDFC0001234)",
      field: "ifsc",
      errorCode: "INVALID_FORMAT",
      disclaimer: FORMAT_VALIDATION_DISCLAIMER,
    };
  }

  return { isValid: true, disclaimer: FORMAT_VALIDATION_DISCLAIMER };
}

export interface OrganizerIdentityValidationResults {
  pan?: ClientValidationResult;
  gstin?: ClientValidationResult;
  ifsc?: ClientValidationResult;
}

export function validateOrganizerIdentity(params: {
  pan?: string | null;
  businessType: BusinessType;
  gstin?: string | null;
  ifsc?: string | null;
}): OrganizerIdentityValidationResults {
  const results: OrganizerIdentityValidationResults = {};

  if (params.pan !== undefined) {
    results.pan = validatePan(params.pan, params.businessType);
  }

  if (params.gstin !== undefined && params.gstin !== null && params.gstin.trim() !== "") {
    const expectedPan =
      params.pan && params.pan.trim().length === 10
        ? params.pan.trim().toUpperCase()
        : undefined;
    results.gstin = validateGstin(params.gstin, expectedPan);
  }

  if (params.ifsc !== undefined && params.ifsc !== null && params.ifsc.trim() !== "") {
    results.ifsc = validateIfsc(params.ifsc);
  }

  return results;
}
