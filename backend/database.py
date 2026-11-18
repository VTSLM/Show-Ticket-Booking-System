from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse, unquote

import ssl
import asyncpg

from config import DATABASE_URL


_pool: Optional[asyncpg.Pool] = None


def _get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _parse_database_url():
    """Parse DATABASE_URL into explicit asyncpg connection parameters."""
    url = urlparse(DATABASE_URL)

    return {
        "host": url.hostname,
        "port": url.port or 5432,
        "user": url.username,
        "password": unquote(url.password or ""),
        "database": url.path.lstrip("/") or "postgres",
    }


async def get_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        db_config = _parse_database_url()

        _pool = await asyncpg.create_pool(
            **db_config,
            min_size=2,
            max_size=10,
            ssl=_get_ssl_context(),
        )

    return _pool


async def close_pool():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None


async def get_conn():
    pool = await get_pool()

    async with pool.acquire() as conn:
        yield conn