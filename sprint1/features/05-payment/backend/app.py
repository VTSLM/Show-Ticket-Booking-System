"""Select the integration adapter from environment configuration.

PAYMENT_STORAGE=postgres selects the shared Supabase/PostgreSQL+Firebase API.
PAYMENT_STORAGE=demo selects the local SQLite sample app for isolated UI testing.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT.parents[1] / ".env", override=False)

storage = os.getenv("PAYMENT_STORAGE", "postgres" if os.getenv("DATABASE_URL", "").strip() else "demo").strip().lower()
if storage == "postgres":
    from backend.shared_main import app
elif storage == "demo":
    from backend.main import app
else:
    raise RuntimeError("PAYMENT_STORAGE must be 'postgres' or 'demo'.")
