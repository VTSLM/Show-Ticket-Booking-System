from fastapi import HTTPException


async def claim_case(conn, case_id: str, reviewer_id: str, lease_minutes: int = 10):
    row = await conn.fetchrow(
        """
        UPDATE venue_verification_cases
           SET reviewer_id = $2,
               claim_expires_at = now() + ($3 * interval '1 minute'),
               status = 'in_review',
               updated_at = now()
         WHERE id = $1
           AND status IN ('submitted', 'in_review')
           AND (
                reviewer_id IS NULL
                OR claim_expires_at <= now()
                OR reviewer_id = $2
           )
        RETURNING id, venue_id, status, reviewer_id, claim_expires_at, version
        """,
        case_id,
        reviewer_id,
        lease_minutes,
    )
    if row is None:
        # Use 404 if the case does not exist; otherwise 409 means another
        # reviewer currently owns it or it is not claimable.
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM venue_verification_cases WHERE id=$1)",
            case_id,
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Review case not found")
        raise HTTPException(status_code=409, detail="Case is not available to claim")
    return dict(row)