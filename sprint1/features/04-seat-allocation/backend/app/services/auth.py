from typing import Optional
from uuid import UUID
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import Header
from app.config import settings
from app.schemas.errors import AppAPIException, ErrorCode
from app.services.db import get_pool
from app.services.logging_config import logger

_firebase_initialized = False

# Deterministic dev UUID for local testing when AUTH_DEV_BYPASS=true
DEV_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
DEV_FIREBASE_UID = "dev-customer-local-uid"


def init_firebase_admin() -> None:
    global _firebase_initialized
    if _firebase_initialized or len(firebase_admin._apps) > 0:
        _firebase_initialized = True
        return

    try:
        if settings.FIREBASE_PROJECT_ID and settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY:
            # Format private key replacing escaped newlines
            pk = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "private_key": pk,
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized with service account credentials.")
        else:
            if settings.AUTH_DEV_BYPASS and settings.ENV == "local":
                logger.info("Firebase Admin not configured; AUTH_DEV_BYPASS is active for local development.")
            else:
                firebase_admin.initialize_app()
                _firebase_initialized = True
                logger.info("Firebase Admin initialized with default credentials.")
    except Exception as exc:
        if settings.AUTH_DEV_BYPASS and settings.ENV == "local":
            logger.warning(f"Firebase Admin initialization warning: {exc}. Dev bypass enabled.")
        else:
            logger.error(f"Failed to initialize Firebase Admin: {exc}")
            raise RuntimeError(f"Failed to initialize Firebase Admin: {exc}")


async def get_or_create_user_uuid(firebase_uid: str, email: Optional[str] = None, name: Optional[str] = None) -> UUID:
    """
    Maps firebase_uid to internal users.id (UUID).
    Creates the row on first login; rejects blocked users.
    All downstream database functions accept users.id, never the Firebase UID.
    """
    pool = get_pool()
    if pool is None:
        # If DB is not configured (e.g. unit test runs), return deterministic UUID based on UID
        if settings.AUTH_DEV_BYPASS and settings.ENV == "local":
            return DEV_USER_ID
        raise AppAPIException(
            status_code=503,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="Database connection unavailable to resolve user identity."
        )

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, is_blocked FROM users WHERE firebase_uid = $1", firebase_uid)
        if row:
            if row["is_blocked"]:
                logger.warning(f"Blocked user attempted login: firebase_uid={firebase_uid}")
                raise AppAPIException(
                    status_code=403,
                    code=ErrorCode.UNAUTHENTICATED,
                    message="Your user account has been suspended. Please contact customer support."
                )
            return row["id"]

        # Insert on first login
        new_row = await conn.fetchrow(
            """
            INSERT INTO users (firebase_uid, email, name)
            VALUES ($1, $2, $3)
            ON CONFLICT (firebase_uid)
            DO UPDATE SET updated_at = NOW()
            RETURNING id, is_blocked;
            """,
            firebase_uid, email, name
        )
        if new_row["is_blocked"]:
            raise AppAPIException(
                status_code=403,
                code=ErrorCode.UNAUTHENTICATED,
                message="Your user account has been suspended."
            )
        logger.info(f"Created new user record: users.id={new_row['id']} for firebase_uid={firebase_uid}")
        return new_row["id"]


async def verify_bearer_token(token: str) -> UUID:
    """Verifies Firebase token and returns internal users.id (UUID)."""
    # Local dev bypass check
    if settings.AUTH_DEV_BYPASS and settings.ENV == "local":
        if token.startswith("dev-") or token.startswith("mock-") or token == "dev-token":
            return await get_or_create_user_uuid(DEV_FIREBASE_UID, "dev@example.com", "Dev Tester")

    try:
        init_firebase_admin()
        decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
        firebase_uid = decoded_token.get("uid")
        if not firebase_uid:
            raise AppAPIException(
                status_code=401,
                code=ErrorCode.UNAUTHENTICATED,
                message="Token payload missing user identifier."
            )
        email = decoded_token.get("email")
        name = decoded_token.get("name")
        return await get_or_create_user_uuid(firebase_uid, email, name)
    except firebase_auth.ExpiredIdTokenError:
        raise AppAPIException(
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
            message="Your session has expired. Please sign in again.",
            details={"reason": "TOKEN_EXPIRED"}
        )
    except (firebase_auth.InvalidIdTokenError, firebase_auth.RevokedIdTokenError, ValueError) as exc:
        raise AppAPIException(
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
            message="Invalid authentication credentials provided.",
            details={"reason": "TOKEN_INVALID"}
        )
    except AppAPIException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected token verification error: {exc}")
        raise AppAPIException(
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
            message="Authentication verification failed."
        )


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> UUID:
    """FastAPI dependency for required authentication."""
    if not authorization:
        raise AppAPIException(
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
            message="Authentication required to hold seats. Please sign in."
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AppAPIException(
            status_code=401,
            code=ErrorCode.UNAUTHENTICATED,
            message="Malformed Authorization header. Format must be 'Bearer <token>'."
        )

    token = parts[1].strip()
    return await verify_bearer_token(token)


async def get_optional_user_id(authorization: Optional[str] = Header(None)) -> Optional[UUID]:
    """FastAPI dependency for optional authentication (used on seat map to compute is_mine)."""
    if not authorization:
        return None

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    try:
        token = parts[1].strip()
        return await verify_bearer_token(token)
    except AppAPIException:
        return None
    except Exception:
        return None
