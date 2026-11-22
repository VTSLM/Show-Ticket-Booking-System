import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    "/app/ticketflow-firebase.json",
)
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:3000",
)

# Chatbot
# Defaults to enabled so existing environments continue to work.
CHAT_ENABLED = os.getenv(
    "CHAT_ENABLED",
    "true",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Email verification (#208): email/password accounts must verify their email before
# using the app. Google accounts are already verified. Switch off only in an emergency.
EMAIL_VERIFICATION_REQUIRED = os.getenv(
    "EMAIL_VERIFICATION_REQUIRED",
    "true",
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# Document Vault configuration (Sprint 2 - A-03)
VERIFICATION_DOCUMENTS_BUCKET = os.getenv(
    "VERIFICATION_DOCUMENTS_BUCKET",
    "verification-documents",
)

MAX_DOCUMENT_SIZE_BYTES = int(
    os.getenv(
        "MAX_DOCUMENT_SIZE_BYTES",
        str(10 * 1024 * 1024),
    )
)

ALLOWED_DOCUMENT_MIME_TYPES = (
    "application/pdf",
    "image/jpeg",
    "image/png",
)

SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes

# ── Role-Based Inactivity Timeout Configuration ──────────────────────────────
# Role-specific inactivity limits: Customer 30m, Manager 20m, Admin 15m.
INACTIVITY_TIMEOUT_CUSTOMER_SECONDS = int(os.getenv("INACTIVITY_TIMEOUT_CUSTOMER_SECONDS", str(30 * 60)))
INACTIVITY_TIMEOUT_MANAGER_SECONDS = int(os.getenv("INACTIVITY_TIMEOUT_MANAGER_SECONDS", str(20 * 60)))
INACTIVITY_TIMEOUT_ADMIN_SECONDS = int(os.getenv("INACTIVITY_TIMEOUT_ADMIN_SECONDS", str(15 * 60)))
INACTIVITY_WARNING_LEAD_SECONDS = int(os.getenv("INACTIVITY_WARNING_LEAD_SECONDS", str(2 * 60)))


def get_role_inactivity_timeout_seconds(roles: list[str]) -> int:
    """Return the inactivity timeout in seconds based on highest privilege role."""
    if not roles:
        return INACTIVITY_TIMEOUT_CUSTOMER_SECONDS
    normalized = [r.lower() for r in roles]
    if "admin" in normalized:
        return INACTIVITY_TIMEOUT_ADMIN_SECONDS
    if "manager" in normalized or "organizer" in normalized:
        return INACTIVITY_TIMEOUT_MANAGER_SECONDS
    return INACTIVITY_TIMEOUT_CUSTOMER_SECONDS


# ── Environment ───────────────────────────────────────────────────────────────
# APP_ENV=production turns on the production checks below, hides the API docs
# and makes the database connection verify the server certificate.
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"


# Browser origins allowed to call the API, comma separated.
CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


# Settings the API must not start without in production.
REQUIRED_IN_PRODUCTION = (
    "DATABASE_URL",
    "CORS_ORIGINS",
    "VERIFICATION_SALT_PEPPER",
    "ADMIN_INVITE_CODE",
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
)


def check_production_settings() -> None:
    """Refuse to start a production server with missing or unsafe settings."""
    if not IS_PRODUCTION:
        return

    missing = [
        name
        for name in REQUIRED_IN_PRODUCTION
        if not os.getenv(name, "").strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing settings for APP_ENV=production: "
            + ", ".join(missing)
        )

    if "*" in CORS_ORIGINS or any(
        origin.startswith("http://") for origin in CORS_ORIGINS
    ):
        raise RuntimeError(
            "CORS_ORIGINS must list https:// origins in production, "
            "not * or http://"
        )

    if os.getenv("DATABASE_SSL", "verify").strip().lower() != "verify":
        raise RuntimeError(
            "DATABASE_SSL must be 'verify' in production"
        )
