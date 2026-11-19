import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, _utils
from config import FIREBASE_SERVICE_ACCOUNT_PATH
import logging
import os
import json

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
            sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            if sa_json:
                cred = credentials.Certificate(json.loads(sa_json))
                firebase_admin.initialize_app(cred)
                _initialized = True
            else:
                try:
                    cred = _utils.EmulatorAdminCredentials()
                    firebase_admin.initialize_app(
                        credential=cred,
                        options={"projectId": "ticketflow-a39bb"}
                    )
                    _initialized = True
                    logger.info("Initialized Firebase Admin with project ticketflow-a39bb (local mode)")
                except Exception as e:
                    logger.warning(f"Could not initialize Firebase Admin: {e}")

def verify_firebase_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its claims.

    Only tokens that the Firebase Admin SDK accepts (signature, issuer, audience
    and expiry) are trusted. To work locally without real accounts, run the
    Firebase Auth emulator and set FIREBASE_AUTH_EMULATOR_HOST; the SDK then
    accepts emulator tokens itself.
    """
    init_firebase()
    if not id_token or not isinstance(id_token, str):
        raise ValueError("Invalid token provided")

    if not firebase_admin._apps:
        raise ValueError("Firebase Admin is not initialised")

    try:
        decoded = firebase_auth.verify_id_token(id_token, clock_skew_seconds=5)
    except Exception as e:
        logger.debug(f"Firebase Admin verify_id_token failed: {e}")
        raise ValueError("Invalid Firebase token") from e

    if not decoded.get("uid"):
        raise ValueError("Invalid Firebase token")
    return decoded


def revoke_refresh_tokens(uid: str) -> None:
    """Sign the user out of every Firebase session (used when an admin blocks them)."""
    init_firebase()
    firebase_auth.revoke_refresh_tokens(uid)
