import hashlib
from typing import Tuple, Optional
import asyncpg

DEFAULT_SYSTEM_TERMS = """1. Admission & Entry:
- Please carry a valid digital or printed copy of your ticket along with government-issued photo identification.
- Entry into the venue begins 45 minutes prior to the scheduled showtime. Late arrivals may be seated only during suitable pauses in performance.

2. Seating & Zones:
- For reserved seating events, tickets are valid only for the designated section, row, and seat number specified.
- For General Admission (GA) and Standing Fan Pit zones, entry is unreserved and granted on a first-come, first-served basis within the allocated zone capacity.

3. Age & Classification:
- Entry is subject to the age rating and certification specified for the event. Attendees must satisfy minimum age requirements upon entry.

4. Cancellation & Refunds:
- Tickets once purchased are subject to the TicketFlow cancellation and refund policy.
- In case of event cancellation or rescheduling by the organizer, refunds will be initiated in accordance with standard platform guidelines.

5. Safety & Conduct:
- Outside food, beverages, and recording equipment are prohibited inside the venue unless explicitly permitted.
- The venue management and organizers reserve the right of admission and may refuse entry or eject individuals displaying disruptive behavior."""


def hash_terms(terms_text: str) -> str:
    """Return a deterministic SHA-256 hash of the terms text."""
    clean = terms_text.strip().replace("\r\n", "\n")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def resolve_show_terms(
    show_terms: Optional[str] = None,
    event_terms: Optional[str] = None
) -> Tuple[str, str, bool]:
    """
    Resolves the active terms for a show.
    Priority: Show-specific terms -> Event-level terms -> TicketFlow System Default terms.
    Returns: (terms_text, terms_hash, is_default)
    """
    if show_terms and show_terms.strip():
        text = show_terms.strip()
        return text, hash_terms(text), False

    if event_terms and event_terms.strip():
        text = event_terms.strip()
        return text, hash_terms(text), False

    default_text = DEFAULT_SYSTEM_TERMS.strip()
    return default_text, hash_terms(default_text), True


async def record_terms_acceptance(
    conn: asyncpg.Connection,
    user_id: str,
    show_id: str,
    terms_hash: str,
    terms_text: str,
    booking_id: Optional[str] = None
) -> dict:
    """
    Records an immutable customer acceptance record with timestamp and exact terms hash.
    """
    row = await conn.fetchrow(
        """INSERT INTO terms_acceptances
           (user_id, show_id, booking_id, terms_hash, terms_text, accepted_at)
           VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, NOW())
           RETURNING id, user_id, show_id, booking_id, terms_hash, accepted_at""",
        user_id, show_id, booking_id, terms_hash, terms_text
    )
    return dict(row)


async def check_terms_acceptance(
    conn: asyncpg.Connection,
    user_id: str,
    show_id: str,
    expected_terms_hash: str,
    booking_id: Optional[str] = None
) -> bool:
    """
    Verifies that the user has explicitly accepted the current version of the show's terms.
    If terms were changed after acceptance, the hashes will mismatch and this returns False.
    """
    if booking_id:
        row = await conn.fetchrow(
            """SELECT id FROM terms_acceptances
               WHERE booking_id=$1::uuid AND user_id=$2::uuid AND terms_hash=$3""",
            booking_id, user_id, expected_terms_hash
        )
        if row:
            return True

    # Fallback to user + show acceptance
    row = await conn.fetchrow(
        """SELECT id FROM terms_acceptances
           WHERE user_id=$1::uuid AND show_id=$2::uuid AND terms_hash=$3
           ORDER BY accepted_at DESC LIMIT 1""",
        user_id, show_id, expected_terms_hash
    )
    return bool(row)
