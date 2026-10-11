import logging
from typing import Any, Dict, List, Optional
import asyncpg
from app.config import get_settings

logger = logging.getLogger("uvicorn.error")

_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> Optional[asyncpg.Pool]:
    global _pool
    settings = get_settings()
    if not settings.DATABASE_URL:
        return None
    if _pool is None:
        try:
            # Ensure SSL mode compatibility with Supabase
            dsn = settings.DATABASE_URL
            # asyncpg prefers direct ssl='require' if connecting to Supabase cloud
            ssl_mode = "require" if ("supabase.co" in dsn or "pooler.supabase.com" in dsn) else None
            
            # Remove any incompatible query parameters for asyncpg if present
            # asyncpg parses dsn directly but does not take pgbouncer=true as connection param
            clean_dsn = dsn.split("?")[0] if "?" in dsn else dsn
            
            _pool = await asyncpg.create_pool(
                dsn=clean_dsn,
                min_size=settings.DB_POOL_MIN_SIZE,
                max_size=settings.DB_POOL_MAX_SIZE,
                ssl=ssl_mode,
                timeout=10,
            )
            logger.info("Successfully connected to Supabase PostgreSQL database pool.")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            _pool = None
            raise e
    return _pool

async def close_db_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed.")

async def fetch_all(query: str, *args) -> List[Dict[str, Any]]:
    pool = await get_db_pool()
    if pool is None:
        raise RuntimeError("DATABASE_URL is not configured in the environment.")
    async with pool.acquire() as conn:
        records = await conn.fetch(query, *args)
        return [dict(r) for r in records]

async def fetch_one(query: str, *args) -> Optional[Dict[str, Any]]:
    pool = await get_db_pool()
    if pool is None:
        raise RuntimeError("DATABASE_URL is not configured in the environment.")
    async with pool.acquire() as conn:
        record = await conn.fetchrow(query, *args)
        return dict(record) if record else None

async def execute(query: str, *args) -> str:
    pool = await get_db_pool()
    if pool is None:
        raise RuntimeError("DATABASE_URL is not configured in the environment.")
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)

async def check_db_health() -> Dict[str, Any]:
    settings = get_settings()
    if not settings.DATABASE_URL:
        return {
            "status": "unconfigured",
            "message": "DATABASE_URL environment variable is missing.",
            "database_connected": False,
        }
    try:
        pool = await get_db_pool()
        if pool is None:
            return {
                "status": "error",
                "message": "Could not create database connection pool.",
                "database_connected": False,
            }
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
            return {
                "status": "healthy",
                "message": "Connected to Supabase PostgreSQL database.",
                "database_connected": (val == 1),
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database error: {str(e)}",
            "database_connected": False,
        }
