import asyncpg
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from app.config import settings
from app.services.logging_config import logger

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> Optional[asyncpg.Pool]:
    """
    Initialize bounded asyncpg connection pool with Supabase pooler compatibility.
    When port 6543 or Supabase transaction pooler is used, statement_cache_size=0 is strictly required.
    """
    global _pool
    if not settings.DATABASE_URL:
        logger.warning("DATABASE_URL is not configured; running without live PostgreSQL pool.")
        return None

    try:
        # Bounded connection pool with statement timeout and cache size 0 for Supabase transaction pooler
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=10.0,
            statement_cache_size=0,
            server_settings={
                "statement_timeout": "5000",  # 5 second query timeout prevents hanging transactions
            }
        )
        logger.info("PostgreSQL asyncpg connection pool initialized successfully.")
        return _pool
    except Exception as exc:
        logger.error(f"Failed to initialize PostgreSQL pool: {exc}")
        if settings.ENV != "local":
            raise
        return None


async def close_db_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL asyncpg connection pool closed.")


def get_pool() -> Optional[asyncpg.Pool]:
    return _pool


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Acquires a single connection from the bounded pool."""
    if _pool is None:
        raise RuntimeError("Database connection pool is not initialized. Check DATABASE_URL configuration.")
    async with _pool.acquire() as conn:
        yield conn


async def check_db_health() -> bool:
    """Verifies database connectivity with a lightweight ping."""
    if _pool is None:
        return False
    try:
        async with _pool.acquire() as conn:
            res = await conn.fetchval("SELECT 1")
            return res == 1
    except Exception as exc:
        logger.error(f"Database health check failed: {exc}")
        return False
