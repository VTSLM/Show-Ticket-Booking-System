"""Lazy Supabase client for manager layout APIs.

Uses the same Supabase project as the customer seat-selection database, but keeps
manager-layout credentials separate from the asyncpg connection pool.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()
from fastapi import HTTPException

@lru_cache(maxsize=1)
def get_supabase():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise HTTPException(
            status_code=503,
            detail="Manager layout database is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY on the backend."
        )
    from supabase import create_client
    return create_client(url, key)
