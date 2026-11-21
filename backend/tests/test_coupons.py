from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.bookings import _price_with_coupon


@pytest.mark.asyncio
async def test_first20_applies_twenty_percent():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "coupon-id",
        "code": "FIRST20",
        "discount_percent": Decimal("20.00"),
    }

    result = await _price_with_coupon(conn, Decimal("100.00"), " first20 ")

    assert result == (
        "coupon-id",
        "FIRST20",
        Decimal("100.00"),
        Decimal("20.00"),
        Decimal("80.00"),
    )


@pytest.mark.asyncio
async def test_invalid_or_inactive_coupon_is_rejected():
    conn = AsyncMock()
    conn.fetchrow.return_value = None

    with pytest.raises(HTTPException) as error:
        await _price_with_coupon(conn, Decimal("100.00"), "NOTVALID")

    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_empty_coupon_keeps_full_price():
    conn = AsyncMock()

    result = await _price_with_coupon(conn, Decimal("100.00"), " ")

    assert result == (
        None,
        None,
        Decimal("100.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    )
    conn.fetchrow.assert_not_awaited()