"""
db.py — Supabase client singleton for TicketFlow backend.

Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env to enable DB persistence.
If either is missing the client will be None and the app runs in demo mode
(in-memory storage only — no data survives a server restart).

Use the service-role key (not the anon key) so the backend can bypass RLS
when writing ticket records from server-side code.
"""

import os
from typing import Optional

try:
    from supabase import create_client, Client
    _supabase_available = True
except ImportError:
    _supabase_available = False

_client: Optional[object] = None
_init_attempted = False


def get_db():
    """
    Returns the Supabase Client, or None if not configured / not installed.
    Logs a one-time warning on first call when running without DB.
    """
    global _client, _init_attempted

    if _init_attempted:
        return _client

    _init_attempted = True

    if not _supabase_available:
        print(
            "[DB] supabase package not installed — running in demo mode.\n"
            "     Install with: pip install supabase"
        )
        return None

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()

    if not url or not key:
        print(
            "[DB] SUPABASE_URL / SUPABASE_SERVICE_KEY not set — "
            "running in demo mode (in-memory only)."
        )
        return None

    try:
        _client = create_client(url, key)
        print("[DB] ✅ Supabase connected")
    except Exception as exc:
        print(f"[DB] ⚠️  Could not connect to Supabase: {exc}\n"
              "     Running in demo mode.")
        _client = None

    return _client
