"""
Services for managing cancellation policies, eligibility, and refund computation.
Follows strict backend calculation: never trust frontend amounts.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import asyncpg


DEFAULT_POLICY = {
    "name": "Standard Platform Cancellation Policy",
    "cutoff_hours": 2,
    "deduction_percentage": 10.0,
    "flat_cancellation_fee": 0.0,
    "is_refundable": True,
    "description": "Cancellations allowed up to 2 hours before showtime with standard 10% processing charge.",
}


async def get_show_cancellation_policy(conn: asyncpg.Connection, show_id: str) -> Dict[str, Any]:
    """
    Fetch the policy assigned to this show or fallback to default platform policy.
    """
    row = await conn.fetchrow(
        """
        SELECT cp.name, cp.cutoff_hours, cp.deduction_percentage,
               cp.flat_cancellation_fee, cp.is_refundable, cp.description
        FROM shows s
        LEFT JOIN cancellation_policies cp ON cp.id = s.cancellation_policy_id
        WHERE s.id = $1::uuid
        """,
        show_id,
    )
    if row and row["name"]:
        return dict(row)

    # Fallback to default policy row in DB
    default_row = await conn.fetchrow(
        """
        SELECT name, cutoff_hours, deduction_percentage,
               flat_cancellation_fee, is_refundable, description
        FROM cancellation_policies
        WHERE is_default = true
        LIMIT 1
        """
    )
    if default_row:
        return dict(default_row)

    return dict(DEFAULT_POLICY)


def evaluate_cancellation_eligibility(
    booking: Dict[str, Any], policy: Dict[str, Any]
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Evaluates whether a booking can be cancelled and calculates the exact refund breakdown.

    Returns:
        (is_eligible, reason_if_not, breakdown_dict)
    """
    status = booking.get("status", "").lower()

    if status == "cancelled":
        return False, "Booking is already cancelled.", {}

    if status not in ("confirmed", "completed"):
        return False, f"Booking status is {status}; only confirmed bookings can be cancelled.", {}

    if not policy.get("is_refundable", True):
        return False, "This event or show is marked as non-refundable.", {}

    start_time: Optional[datetime] = booking.get("start_time")
    if not start_time:
        return False, "Show timing information is unavailable.", {}

    # Ensure timezone-aware UTC comparison
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    if now >= start_time:
        return False, "Show has already started or passed.", {}

    cutoff_hours = int(policy.get("cutoff_hours", 2))
    cutoff_time = start_time - timedelta(hours=cutoff_hours)

    if now >= cutoff_time:
        return (
            False,
            f"Cancellation deadline has passed. Cancellations must be made at least {cutoff_hours} hours prior to showtime.",
            {},
        )

    # Calculate Breakdown
    total_paid = float(booking.get("paid_amount") or booking.get("total_amount") or 0.0)
    has_payment = booking.get("payment_id") is not None and (
        booking.get("payment_status") == "successful" or booking.get("payment_status") == "refunded"
    )

    if not has_payment or total_paid <= 0:
        return (
            True,
            "",
            {
                "ticket_amount": float(booking.get("total_amount", 0.0)),
                "cancellation_charge": 0.0,
                "expected_refund": 0.0,
                "has_payment": False,
                "cutoff_time": cutoff_time.isoformat(),
                "policy_name": policy.get("name"),
                "policy_description": policy.get("description"),
            },
        )

    deduction_pct = float(policy.get("deduction_percentage", 0.0))
    flat_fee = float(policy.get("flat_cancellation_fee", 0.0))

    percentage_charge = round((total_paid * deduction_pct) / 100.0, 2)
    cancellation_charge = round(percentage_charge + flat_fee, 2)

    # Ensure cancellation charge does not exceed total paid
    cancellation_charge = min(cancellation_charge, total_paid)
    expected_refund = round(total_paid - cancellation_charge, 2)

    return (
        True,
        "",
        {
            "ticket_amount": total_paid,
            "cancellation_charge": cancellation_charge,
            "expected_refund": expected_refund,
            "has_payment": True,
            "cutoff_time": cutoff_time.isoformat(),
            "policy_name": policy.get("name"),
            "policy_description": policy.get("description"),
        },
    )
