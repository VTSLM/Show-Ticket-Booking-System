"""
Risk Assessment Engine — Sprint 2: Deliverable A-05.
Person A: Organizer Verification & Compliance.

Evaluates validation results, duplicate collisions, and bank verification outcomes
to produce an advisory risk assessment report for administrative reviewers.
Does NOT automatically approve or reject applicants.
"""

from typing import Any, Dict, List, Optional
from models.verification import BusinessType


def assess_organizer_risk(
    profile: Dict[str, Any],
    bank_account: Optional[Dict[str, Any]],
    bank_verification_result: Optional[Dict[str, Any]],
    duplicate_collisions: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Computes a comprehensive risk score (0-100) and list of risk flags.
    
    Risk Levels:
    - LOW: 0 - 29 (Standard profile, normal workflow)
    - MEDIUM: 30 - 59 (Reviewer attention recommended)
    - HIGH: 60 - 100 (Requires careful administrative scrutiny)
    """
    risk_score = 0
    flags = []

    # 1. Duplicate Collisions (High Risk)
    if duplicate_collisions:
        for col in duplicate_collisions:
            kind = col.get("kind", "IDENTIFIER")
            flags.append({
                "code": f"DUPLICATE_{kind}_COLLISION",
                "severity": "HIGH",
                "description": f"Duplicate {kind} fingerprint detected matching another case ({col.get('colliding_case_id')}).",
                "weight": 50,
            })
            risk_score += 50

    # 2. Bank Verification Status
    if bank_verification_result:
        status = bank_verification_result.get("status")
        if status == "NAME_MISMATCH":
            flags.append({
                "code": "BANK_NAME_MISMATCH",
                "severity": "MEDIUM",
                "description": "Account holder name differs from registered name at destination bank.",
                "weight": 25,
            })
            risk_score += 25
        elif status == "INVALID_IFSC":
            flags.append({
                "code": "INVALID_BANK_IFSC",
                "severity": "HIGH",
                "description": "Bank IFSC code is invalid or unrecognized.",
                "weight": 30,
            })
            risk_score += 30
        elif status == "FAILED":
            flags.append({
                "code": "BANK_VALIDATION_FAILED",
                "severity": "HIGH",
                "description": "Destination bank rejected penny-drop validation.",
                "weight": 35,
            })
            risk_score += 35
    elif not bank_account or not bank_account.get("verified"):
        flags.append({
            "code": "UNVERIFIED_BANK_ACCOUNT",
            "severity": "LOW",
            "description": "Bank account has not yet undergone penny-drop or administrative verification.",
            "weight": 15,
        })
        risk_score += 15

    # 3. PAN and GSTIN Entity Alignment
    pan_masked = profile.get("pan_masked") or ""
    gstin_masked = profile.get("gstin_masked") or ""
    business_type = profile.get("business_type")

    # If Company or LLP and no GSTIN
    if business_type in (BusinessType.COMPANY.value, BusinessType.LLP.value, "COMPANY", "LLP") and not gstin_masked:
        flags.append({
            "code": "MISSING_GSTIN_FOR_CORPORATE",
            "severity": "MEDIUM",
            "description": f"Entity classification {business_type} requires valid GSTIN registration.",
            "weight": 20,
        })
        risk_score += 20

    # 4. Document Rejection History
    rejected_docs = [d for d in documents if d.get("review_status") == "REJECTED"]
    if rejected_docs:
        flags.append({
            "code": "PREVIOUS_DOCUMENT_REJECTIONS",
            "severity": "MEDIUM",
            "description": f"{len(rejected_docs)} document(s) have been rejected in previous review rounds.",
            "weight": 15,
        })
        risk_score += 15

    # Clamp score to 0 - 100
    risk_score = min(100, max(0, risk_score))

    # Derive overall level
    if risk_score >= 60:
        risk_level = "HIGH"
    elif risk_score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "flags_count": len(flags),
        "flags": flags,
        "recommendation": (
            "Reviewer caution required: review duplicate collisions and bank verification."
            if risk_level == "HIGH"
            else "Standard review process."
        ),
    }

