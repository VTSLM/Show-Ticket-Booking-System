import os
import asyncio
import pytest
from app.config import settings

# Explicitly configure settings for local test execution
settings.ENV = "local"
settings.AUTH_DEV_BYPASS = True
settings.ENABLE_DEV_PAYMENT_SIMULATOR = True

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as tc:
        yield tc


def check_is_db_live() -> bool:
    """Synchronous probe to verify PostgreSQL connectivity."""
    if not settings.DATABASE_URL:
        return False
    try:
        import asyncpg
        async def _probe():
            conn = await asyncpg.connect(settings.DATABASE_URL, timeout=2.0, statement_cache_size=0)
            await conn.execute("SELECT 1")
            await conn.close()
        asyncio.run(_probe())
        return True
    except Exception:
        return False
