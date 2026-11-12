import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import logging
import os

logger = logging.getLogger("uvicorn.error")
_initialized = False

def init_firebase():
    global _initialized
    if not _initialized and not firebase_admin._apps:
        if os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
            cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
            firebase_admin.initialize_app(cred)
            _initialized = True
        else:
            # Try environment variable fallback
            import json
            sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
                firebase_admin.initialize_app(cred)
                _initialized = True
            else:
                logger.warning(
                    f"Firebase service account not found at {FIREBASE_SERVICE_ACCOUNT_PATH}. "
                    "Running in local development mode without Firebase service account."
                )

def verify_firebase_token(id_token: str) -> dict:
    init_firebase()
    if not firebase_admin._apps:
        if id_token.startswith("dev-") or id_token == "test-token":
            return {"uid": id_token.replace("dev-", "")}
        raise RuntimeError(f"Firebase service account not found at {FIREBASE_SERVICE_ACCOUNT_PATH}")
    return firebase_auth.verify_id_token(
        id_token,
        clock_skew_seconds=5
    )
