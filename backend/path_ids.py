"""
Reject malformed ids in URLs before any database query (#140).

Every id in this API is a UUID. A path parameter whose name ends in ``_id``
(``booking_id``, ``show_id``, ...) that is not a valid UUID can never match a
row, so the request gets a plain 404 instead of reaching Postgres, where the
``$1::uuid`` cast would fail and turn into a 500.

Registered once for the whole app in ``main.py``, so new routes are covered too.
"""
import uuid

from fastapi import HTTPException, Request


def is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


async def validate_path_ids(request: Request) -> None:
    for name, value in request.path_params.items():
        if name.endswith("_id") and not is_uuid(value):
            raise HTTPException(status_code=404, detail="Not found")
