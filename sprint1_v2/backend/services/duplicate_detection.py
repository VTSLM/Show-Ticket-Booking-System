"""
Duplicate Detection Service — Sprint 2: Deliverable A-05.
Person A & Shared Foundations.

Provides salted fingerprint generation, collision detection, and registration
using the shared `duplicate_fingerprints` table.
Ensures raw sensitive identifiers (PAN, GSTIN, Bank Accounts) are never stored or exposed.
"""

from typing import Any, Dict, List, Optional
import uuid
import asyncpg
from models.verification import CaseType, FingerprintKind
from services.verification_security import hash_salted_value


async def check_duplicate_collisions(
    conn: asyncpg.Connection,
    case_id: uuid.UUID,
    pan: Optional[str] = None,
    gstin: Optional[str] = None,
    bank_account: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Check if PAN, GSTIN, or Bank Account salted hashes collide with an existing case.
    Returns collision records (kind, colliding case_id, case_type) without exposing values.
    """
    hashes_to_check = []
    if pan and pan.strip():
        hashes_to_check.append((FingerprintKind.PAN.value, hash_salted_value(pan.strip())))
    if gstin and gstin.strip():
        hashes_to_check.append((FingerprintKind.GSTIN.value, hash_salted_value(gstin.strip())))
    if bank_account and bank_account.strip():
        hashes_to_check.append((FingerprintKind.BANK_ACCOUNT.value, hash_salted_value(bank_account.strip(), salt="tf_bank_salt")))

    collisions = []
    for kind, salted_hash in hashes_to_check:
        row = await conn.fetchrow(
            """
            SELECT id, kind, case_id, case_type, created_at
            FROM duplicate_fingerprints
            WHERE kind = $1 AND salted_hash = $2 AND case_id != $3
            """,
            kind,
            salted_hash,
            case_id,
        )
        if row:
            collisions.append({
                "kind": row["kind"],
                "colliding_case_id": str(row["case_id"]),
                "colliding_case_type": row["case_type"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

    return collisions


async def register_case_fingerprints(
    conn: asyncpg.Connection,
    case_id: uuid.UUID,
    case_type: CaseType = CaseType.ORGANIZER,
    pan: Optional[str] = None,
    gstin: Optional[str] = None,
    bank_account: Optional[str] = None,
) -> int:
    """
    Register or update salted fingerprints for a verified/submitted case in `duplicate_fingerprints`.
    Returns count of fingerprints registered.
    """
    registered = 0

    items = []
    if pan:
        p_str = str(pan).strip()
        if p_str:
            items.append((FingerprintKind.PAN.value, hash_salted_value(p_str)))
    if gstin:
        g_str = str(gstin).strip()
        if g_str:
            items.append((FingerprintKind.GSTIN.value, hash_salted_value(g_str)))
    if bank_account:
        b_str = str(bank_account).strip()
        if b_str:
            items.append((FingerprintKind.BANK_ACCOUNT.value, hash_salted_value(b_str, salt="tf_bank_salt")))

    for kind, salted_hash in items:
        # Check if already registered for this case
        existing = await conn.fetchrow(
            "SELECT id FROM duplicate_fingerprints WHERE kind = $1 AND case_id = $2",
            kind,
            case_id,
        )
        if existing:
            await conn.execute(
                """
                UPDATE duplicate_fingerprints
                SET salted_hash = $1
                WHERE id = $2
                """,
                salted_hash,
                existing["id"],
            )
        else:
            await conn.execute(
                """
                INSERT INTO duplicate_fingerprints (kind, salted_hash, case_id, case_type)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (kind, salted_hash) DO NOTHING
                """,
                kind,
                salted_hash,
                case_id,
                case_type.value,
            )
        registered += 1

    return registered
