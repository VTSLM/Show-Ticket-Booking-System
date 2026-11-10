# TicketFlow — Sprint 2: Organizer Verification Foundation (Deliverable A-01)

> **Module:** Admin & Organizer Verification  
> **Deliverable:** Person A: A-01 (Organizer Verification Foundation & Shared Contracts)  
> **Collaborator:** Person B (Venue Verification Integration)  
> **Target Environment:** `sprint1_v2` Unified Codebase  

---

## 1. Overview & Architecture

The **Organizer & Business Verification module** provides the trust, compliance, and anti-fraud backbone for event organizers on TicketFlow. 

In Sprint 2, the verification system is divided between **Person A (Organizer & Business Verification)** and **Person B (Venue Verification)** under a shared architecture:
- **Person A owns**: The organizer-specific data models (`organizer_profiles`, `bank_accounts`, `trust_tier_rules`), security tokenization/masking algorithms, and the **shared core foundations** (`verification_documents`, `duplicate_fingerprints`, `notifications`).
- **Person B reuses**: The shared polymorphic document engine (`verification_documents`), the salted hash deduplication store (`duplicate_fingerprints`), and the unified notification dispatcher (`notifications`) without duplicating code or tables.

```
                              ┌─────────────────────────┐
                              │       users (auth)      │
                              └────────────┬────────────┘
                                           │ 1:1
                                           ▼
┌──────────────────────┐      ┌─────────────────────────┐      ┌──────────────────────────┐
│   trust_tier_rules   ├─────►│   organizer_profiles    │◄─────┤      bank_accounts       │
└──────────────────────┘      └────────────┬────────────┘      └──────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                             │
                    ▼                                             ▼
       ┌─────────────────────────┐                   ┌──────────────────────────┐
       │ verification_documents  │                   │  duplicate_fingerprints  │
       │   (Polymorphic Store)   │                   │   (Collision Detection)  │
       │                         │                   │                          │
       │ • Case: ORGANIZER (A)   │                   │ • Case: ORGANIZER (A)    │
       │ • Case: VENUE (B)       │                   │ • Case: VENUE (B)        │
       │ • Case: LISTING         │                   │ • Case: LISTING          │
       └─────────────────────────┘                   └──────────────────────────┘
```

---

## 2. Contracts & Enums

### 2.1 Business Types (`BusinessType`)
Entity categories allowed for organizer registration:
- `INDIVIDUAL`: Sole practitioner / freelance event host.
- `SOLE_PROPRIETOR`: Unincorporated business entity.
- `COMPANY`: Private or Public Limited Company (incorporated under Companies Act).
- `LLP`: Limited Liability Partnership.
- `TRUST`: Charitable trust or cultural non-profit society.

### 2.2 Case Types (`CaseType` - Shared with Person B)
Polymorphic verification scopes:
- `ORGANIZER`: Organizer KYC and business identity (Person A).
- `VENUE`: Cinema, auditorium, or stadium physical venue compliance (Person B).
- `LISTING`: Specific show or high-value event verification.

### 2.3 Document Types (`DocumentType` - Shared Catalogue)
Unified enum covering both Person A and Person B requirements:
| Category | Type Code | Description | Typical Owner |
|---|---|---|---|
| **Organizer KYC** | `PAN` | Permanent Account Number Card | Person A |
| **Organizer KYC** | `GST_CERTIFICATE` | Form GST REG-06 | Person A |
| **Organizer KYC** | `BANK_PROOF` | Cancelled Cheque / Account Statement | Person A |
| **Organizer KYC** | `SIGNATORY_ID` | Aadhaar/Passport of Authorized Signatory | Person A |
| **Organizer KYC** | `AUTHORISATION_LETTER` | Board Resolution / Power of Attorney | Person A |
| **Organizer KYC** | `BUSINESS_REGISTRATION` | Certificate of Incorporation / Trust Deed | Person A |
| **Venue Safety** | `CINEMA_LICENCE` | District Magistrate / Police Cinema Licence | Person B |
| **Venue Safety** | `FIRE_NOC` | Fire Department No Objection Certificate | Person B |
| **Venue Safety** | `ELECTRICAL_CERT` | Chief Electrical Inspectorate Certificate | Person B |
| **Venue Safety** | `OCCUPANCY_CERT` | Municipal Occupancy / Building Completion | Person B |
| **Venue Safety** | `OWNERSHIP_PROOF` | Property Deed or Registered Lease Agreement | Person B |
| **General** | `OTHER` | Miscellaneous supporting affidavits | Person A / B |

### 2.4 Status Lifecycles
- **`VerificationStatus`**: `DRAFT` → `PENDING` → `CHANGES_REQUESTED` ↔ `APPROVED` / `REJECTED` / `SUSPENDED`
- **`ReviewStatus`**: `PENDING` → `CHANGES_REQUESTED` ↔ `APPROVED` / `REJECTED`
- **`TrustTierCode`**: `TIER_1` (Starter), `TIER_2` (Established), `TIER_3` (High Volume / Trusted)

---

## 3. Database Schema

### 3.1 `trust_tier_rules`
Defines operational velocity limits and settlement rules per trust level.
- `tier` (varchar(50) PK): e.g., `'TIER_1'`, `'TIER_2'`, `'TIER_3'`.
- `max_live_shows` (integer): Maximum concurrent live shows an organizer can list.
- `payout_hold_days` (integer): Days ticket revenue is escrowed after event completion.
- `rules` (jsonb): Dynamic parameters (`instant_payout`, `ticket_price_limit`, etc.).

### 3.2 `organizer_profiles`
Main identity profile linked 1:1 with `users(id)`.
- `id` (uuid PK): Gen random UUID.
- `user_id` (uuid FK -> users.id): Unique constraint; cascade delete on user removal.
- `legal_name` (varchar(255)): Official registered trade or entity name.
- `business_type` (varchar(50)): CHECK in `('INDIVIDUAL', 'SOLE_PROPRIETOR', 'COMPANY', 'LLP', 'TRUST')`.
- `state` (varchar(100)): Jurisdiction of operations.
- `pan_masked` (varchar(20)): Masked format (e.g. `ABCDE****F`). Never plaintext.
- `gstin_masked` (varchar(20)): Masked format (e.g. `24ABCDE****1Z5`).
- `verification_status` (varchar(30)): Current state in review pipeline.
- `trust_tier` (varchar(50) FK -> trust_tier_rules.tier): Assigned trust tier.

### 3.3 `bank_accounts`
Organizer payout settlement accounts.
- `id` (uuid PK).
- `organizer_id` (uuid FK -> organizer_profiles.id).
- `holder_name` (varchar(255)).
- `ifsc` (varchar(20)).
- `account_masked` (varchar(30)): Masked string keeping only last 4 digits (e.g. `********9012`).
- `account_hash` (varchar(128)): Deterministic salted HMAC-SHA256 for duplicate bank account fraud detection.
- `verified` (boolean): Whether penny-drop or administrative check passed.

### 3.4 `verification_documents` (Shared with Person B)
Polymorphic document tracking for both Organizers and Venues.
- `id` (uuid PK).
- `case_id` (uuid): Targets `organizer_profiles.id` when `case_type='ORGANIZER'`, or `venues.id` when `case_type='VENUE'`.
- `case_type` (varchar(30)): CHECK in `('ORGANIZER', 'VENUE', 'LISTING')`.
- `doc_type` (varchar(50)): Document classification from shared enum.
- `version` (integer): Version sequence (defaults to 1).
- `storage_ref` (text): Internal secure vault path (e.g. `vault/organizers/{id}/pan_v1.pdf`).
- `doc_number_masked` (varchar(50)): Masked document reference.
- `review_status` (varchar(30)): Review outcome (`PENDING`, `APPROVED`, etc.).
- `reviewer_comment` (text): Feedback if changes are requested or rejected.

### 3.5 `duplicate_fingerprints` (Shared Anti-fraud Collision Store)
Cross-account collision detection without storing sensitive plaintext.
- `id` (uuid PK).
- `kind` (varchar(50)): Attribute type (`PAN`, `GSTIN`, `BANK_ACCOUNT`, `CINEMA_LICENCE`, etc.).
- `salted_hash` (varchar(128)): HMAC-SHA256 hash.
- `case_id` (uuid).
- `case_type` (varchar(30)): `ORGANIZER` or `VENUE`.
- `UNIQUE (kind, salted_hash)`: Database-enforced duplicate prevention.

### 3.6 `notifications` (Shared Event Dispatch Foundation)
- `id` (uuid PK).
- `user_id` (uuid FK -> users.id).
- `event_name` (varchar(100)): e.g. `organizer.approved`, `venue.verification_rejected`.
- `payload` (jsonb): Contextual event data.
- `read_at` / `emailed_at` (timestamptz): Delivery tracking.

---

## 4. Security & Privacy Guarantees

1. **Zero Plaintext Storage**: Full PAN, GSTIN, and Bank Account numbers are never stored in the database.
2. **Masking**:
   - PAN: `mask_pan("ABCDE1234F")` → `ABCDE****F`
   - GSTIN: `mask_gstin("24ABCDE1234F1Z5")` → `24ABCDE****1Z5`
   - Bank Account: `mask_bank_account("50100234564589")` → `**********4589`
3. **Collision Detection via Salted Hashes**:
   - `hash_salted_value(raw_value)` generates a deterministic 64-character SHA-256 HMAC using an application pepper.
   - Fraudulent organizers cannot register a second account using the same PAN or bank account.
4. **Row Level Security (RLS)**:
   - All 6 tables have RLS enabled to prevent direct unauthorized access via client-side Supabase keys.

---

## 5. Person B (Venue Verification) Integration Guide

Person B can directly utilize the shared foundations without creating any duplicate tables or enums:

1. **Documents**:
   ```python
   from models.verification import CaseType, DocumentType, VerificationDocumentCreate

   venue_fire_noc = VerificationDocumentCreate(
       case_id=venue_uuid,
       case_type=CaseType.VENUE,
       doc_type=DocumentType.FIRE_NOC,
       storage_ref="vault/venues/123/fire_noc_2026.pdf",
       doc_number_masked="NOC-2026-****-AHM",
       issued_by="Gujarat Fire Service",
       valid_to=date(2027, 12, 31)
   )
   ```

2. **Deduplication / Anti-Collision**:
   ```python
   from models.verification import CaseType, DuplicateFingerprintCreate
   from services.verification_security import hash_salted_value

   licence_fp = DuplicateFingerprintCreate(
       kind="CINEMA_LICENCE",
       salted_hash=hash_salted_value(raw_licence_number),
       case_id=venue_uuid,
       case_type=CaseType.VENUE
   )
   ```

3. **Notifications**:
   ```python
   from models.verification import NotificationCreate

   venue_notif = NotificationCreate(
       user_id=manager_user_uuid,
       event_name="venue.verification_approved",
       payload={"venue_id": str(venue_uuid), "venue_name": "Regal Multiplex"}
   )
   ```

---

## 6. Migration & Rollback Guide

- **Apply Migration**: Execute `sprint1_v2/database/004_organizer_verification.sql` in Supabase / PostgreSQL.
- **Load Fixtures**: Execute `sprint1_v2/database/seeds/002_organizer_verification_fixtures.sql`.
- **Rollback (if needed)**: Execute `sprint1_v2/database/004_organizer_verification_rollback.sql`.

