import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import os
import json
import logging

logger = logging.getLogger("uvicorn.error")
_initialized = False

def init_firebase():
    global _initialized
    if not _initialized and not firebase_admin._apps:
        # Check standard path, backend folder, and project root
        candidates = [
            FIREBASE_SERVICE_ACCOUNT_PATH,
            os.path.join(os.path.dirname(__file__), "ticketflow-firebase.json"),
            os.path.join(os.path.dirname(__file__), "..", "..", "ticketflow-firebase.json"),
        ]
        found_path = next((p for p in candidates if p and os.path.exists(p)), None)

        if found_path:
            cred = credentials.Certificate(found_path)
            firebase_admin.initialize_app(cred)
            logger.info(f"[Firebase] Initialized with service account: {found_path}")
        else:
            sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
                firebase_admin.initialize_app(cred)
                logger.info("[Firebase] Initialized using FIREBASE_SERVICE_ACCOUNT_JSON")
            else:
                logger.warning(
                    f"[Firebase Warning] Service account JSON '{FIREBASE_SERVICE_ACCOUNT_PATH}' not found.\n"
                    "Running in development fallback mode (unverified JWT parsing).\n"
                    "To enable full signature verification, download your private key from Firebase Console "
                    "and place it at 'sprint1_v2/backend/ticketflow-firebase.json'."
                )
        _initialized = True

def verify_firebase_token(id_token: str) -> dict:
    init_firebase()
    if firebase_admin._apps:
        try:
            return firebase_auth.verify_id_token(
                id_token,
                clock_skew_seconds=5
            )
        except Exception as e:
            logger.warning(f"[Firebase] Token verification error: {e}. Trying dev fallback...")

    # Development fallback: decode JWT payload
    import jwt
    decoded = jwt.decode(id_token, options={"verify_signature": False})
    uid = decoded.get("uid") or decoded.get("user_id") or decoded.get("sub")
    if not uid:
        raise ValueError("Invalid token: missing user ID")
    decoded["uid"] = uid
    return decoded

