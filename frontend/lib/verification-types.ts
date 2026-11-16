/**
 * Verification Types & Shared Contracts — Sprint 2.
 * Person A: Organizer Verification Foundation & Shared Foundations (Person B Venue integration).
 */

export type BusinessType =
  | "INDIVIDUAL"
  | "SOLE_PROPRIETOR"
  | "COMPANY"
  | "LLP"
  | "TRUST";

export type CaseType = "ORGANIZER" | "VENUE" | "LISTING";

export type DocumentType =
  // Organizer documents (Person A)
  | "PAN"
  | "GST_CERTIFICATE"
  | "BANK_PROOF"
  | "SIGNATORY_ID"
  | "AUTHORISATION_LETTER"
  | "BUSINESS_REGISTRATION"
  // Venue documents (Person B)
  | "CINEMA_LICENCE"
  | "FIRE_NOC"
  | "ELECTRICAL_CERT"
  | "OCCUPANCY_CERT"
  | "OWNERSHIP_PROOF"
  // Fallback
  | "OTHER";

export type VerificationStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "IN_REVIEW"
  | "PENDING"
  | "CHANGES_REQUESTED"
  | "APPROVED"
  | "REJECTED"
  | "SUSPENDED"
  | "EXPIRED";

export type ReviewStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "CHANGES_REQUESTED";

export type TrustTierCode = "TIER_1" | "TIER_2" | "TIER_3";

export interface TrustTierRule {
  tier: string;
  max_live_shows: number;
  payout_hold_days: number;
  rules: Record<string, any>;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

export interface OrganizerProfile {
  id: string;
  user_id: string;
  legal_name: string;
  business_type: BusinessType;
  state?: string;
  pan_masked?: string;
  gstin_masked?: string;
  verification_status: VerificationStatus;
  trust_tier: string;
  created_at: string;
  updated_at: string;
}

export interface BankAccount {
  id: string;
  organizer_id: string;
  holder_name: string;
  ifsc: string;
  account_masked: string;
  account_hash: string;
  verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface VerificationDocument {
  id: string;
  case_id: string;
  case_type: CaseType;
  doc_type: DocumentType;
  version: number;
  storage_ref: string;
  doc_number_masked?: string;
  issued_by?: string;
  valid_to?: string;
  review_status: ReviewStatus;
  reviewer_comment?: string;
  uploaded_by?: string;
  uploaded_at: string;
  reviewed_by?: string;
  reviewed_at?: string;
}

export interface DuplicateFingerprint {
  id: string;
  kind: string;
  salted_hash: string;
  case_id: string;
  case_type: CaseType;
  created_at: string;
}

export interface Notification {
  id: string;
  user_id: string;
  event_name: string;
  payload: Record<string, any>;
  read_at?: string;
  emailed_at?: string;
  created_at: string;
}

