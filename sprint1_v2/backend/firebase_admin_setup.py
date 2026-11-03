import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import os

_initialized = False

def init_firebase():
    global _initialized
    if not _initialized and not firebase_admin._apps:
        if os.path.exists(FIREBASE_SERVICE_ACCOUNT_PATH):
            cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
            firebase_admin.initialize_app(cred)
        else:
            # Try environment variable fallback
            import json
            sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
                firebase_admin.initialize_app(cred)
            else:
                raise RuntimeError(f"Firebase service account not found at {FIREBASE_SERVICE_ACCOUNT_PATH}")
        _initialized = True

def verify_firebase_token(id_token: str) -> dict:
    init_firebase()
    return firebase_auth.verify_id_token(id_token)
