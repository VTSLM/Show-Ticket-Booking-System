"""
Trust Tier & Payout Eligibility Service — Sprint 2: Deliverable A-06.
Person A: Organizer Verification & Compliance.

Enforces trust tier limits and payout settlement eligibility based on:
1. Verification status (must be APPROVED).
2. User account state (active vs suspended / blocked).
3. Verified bank account presence.
4. Configured trust tier parameters from `trust_tier_rules`.
"""

from typing import Any, Dict, List, Optional
import uuid
import asyncpg
from models.verification import VerificationStatus


async def get_trust_tier_rules(
    conn: asyncpg.Connection,
    tier_name: str = "TIER_1",
) -> Dict[str, Any]:
    """Retrieve rule configuration from `trust_tier_rules`."""
    row = await conn.fetchrow(
        """
        SELECT tier, max_live_shows, payout_hold_days, rules, description
        FROM trust_tier_rules
        WHERE tier = $1
        """,
        tier_name,
    )
    if row:
        res = dict(row)
        if isinstance(res.get("rules"), str):
            import json
            try:
                res["rules"] = json.loads(res["rules"])
            except Exception:
                res["rules"] = {}
        return res

    # Baseline fallback defaults
    return {
        "tier": tier_name,
        "max_live_shows": 2,
        "payout_hold_days": 14,
        "rules": {"instant_payout": False, "ticket_price_limit": 5000},
        "description": "Default starter tier",
    }


async def evaluate_payout_eligibility(
    conn: asyncpg.Connection,
    organizer_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Evaluates whether an organizer is currently eligible for payout settlements.
    
    Checks:
    - Verification status must be 'APPROVED'
    - Organizer must not be 'SUSPENDED'
    - User account must be 'active'
    - Verified bank account must exist
    - Reads hold period and restrictions from `trust_tier_rules`
    """
    # 1. Fetch organizer profile and user state
    prof = await conn.fetchrow(
        """
        SELECT o.id, o.user_id, o.legal_name, o.verification_status, o.trust_tier,
               o.suspension_reason, u.status as user_status
        FROM organizer_profiles o
        JOIN users u ON u.id = o.user_id
        WHERE o.id = $1
        """,
        organizer_id,
    )
    if not prof:
        return {
            "eligible": False,
            "organizer_id": str(organizer_id),
            "verification_status": "NOT_FOUND",
            "trust_tier": "NONE",
            "reasons": ["Organizer profile not found."],
        }

    reasons: List[str] = []
    eligible = True
    v_status = prof["verification_status"]
    u_status = prof["user_status"]
    tier = prof["trust_tier"] or "TIER_1"

    # Rule 1: Verification status check
    if v_status == VerificationStatus.SUSPENDED.value:
        eligible = False
        reasons.append(f"Organizer account is suspended. Reason: {prof.get('suspension_reason') or 'Administrative hold'}")
    elif v_status != VerificationStatus.APPROVED.value:
        eligible = False
        reasons.append(f"Organizer is not approved (current status: '{v_status}'). Complete verification first.")

    # Rule 2: User account status
    if u_status != "active":
        eligible = False
        reasons.append(f"User account is '{u_status}'. Active account required.")

    # Rule 3: Bank account check
    bank = await conn.fetchrow(
        """
        SELECT id, holder_name, ifsc, account_masked, verified
        FROM bank_accounts
        WHERE organizer_id = $1
        ORDER BY created_at DESC LIMIT 1
        """,
        organizer_id,
    )
    if not bank:
        eligible = False
        reasons.append("No settlement bank account linked. Bank account registration required.")
    elif not bank["verified"]:
        eligible = False
        reasons.append("Bank account verification is pending or unconfirmed.")

    # Rule 4: Trust Tier Rules
    tier_info = await get_trust_tier_rules(conn, tier)
    payout_hold_days = tier_info.get("payout_hold_days", 14)
    rules_dict = tier_info.get("rules", {})
    instant_payout = rules_dict.get("instant_payout", False)
    price_limit = rules_dict.get("ticket_price_limit", 5000)

    if eligible:
        reasons.append(f"Organizer verified under {tier}. Payout hold: {payout_hold_days} days after show completion.")
        if instant_payout:
            reasons.append("Instant settlement enabled for this trust tier.")

    return {
        "eligible": eligible,
        "organizer_id": str(organizer_id),
        "legal_name": prof["legal_name"],
        "verification_status": v_status,
        "trust_tier": tier,
        "max_live_shows": tier_info.get("max_live_shows", 2),
        "payout_hold_days": payout_hold_days,
        "instant_payout": instant_payout,
        "ticket_price_limit": price_limit,
        "reasons": reasons,
        "bank_account_masked": bank["account_masked"] if bank else None,
    }


async def check_live_show_limit(
    conn: asyncpg.Connection,
    organizer_id: uuid.UUID,
) -> Dict[str, Any]:
    """
    Check if the organizer has reached their maximum allowed live shows under their trust tier.
    """
    prof = await conn.fetchrow(
        "SELECT id, user_id, verification_status, trust_tier FROM organizer_profiles WHERE id = $1",
        organizer_id,
    )
    if not prof or prof["verification_status"] != "APPROVED":
        return {
            "allowed": False,
            "max_live_shows": 0,
            "current_live_shows": 0,
            "reason": "Only verified organizers can publish live shows.",
        }

    tier = prof["trust_tier"] or "TIER_1"
    tier_rules = await get_trust_tier_rules(conn, tier)
    max_shows = tier_rules.get("max_live_shows", 2)

    # Count active shows for this user/organizer
    # Query shows where event organizer matches user
    user_id = prof["user_id"]
    active_count = await conn.fetchval(
        """
        SELECT count(*)
        FROM shows s
        JOIN events e ON e.id = s.event_id
        WHERE e.manager_id = $1 AND s.start_time >= now()
        """,
        user_id,
    ) or 0

    allowed = active_count < max_shows
    return {
        "allowed": allowed,
        "trust_tier": tier,
        "max_live_shows": max_shows,
        "current_live_shows": active_count,
        "remaining_slots": max(0, max_shows - active_count),
        "reason": "Quota available" if allowed else f"Trust tier {tier} maximum active show limit ({max_shows}) reached.",
    }

