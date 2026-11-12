import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres.nvgghebapzhxzrwunwrj:REDACTED_DB_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://nvgghebapzhxzrwunwrj.supabase.co"
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or "REDACTED_SUPABASE_JWT"
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or "REDACTED_SUPABASE_JWT"
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "/app/ticketflow-firebase.json")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Document Vault configuration (Sprint 2 - A-03)
VERIFICATION_DOCUMENTS_BUCKET = os.getenv("VERIFICATION_DOCUMENTS_BUCKET", "verification-documents")
MAX_DOCUMENT_SIZE_BYTES = int(os.getenv("MAX_DOCUMENT_SIZE_BYTES", str(10 * 1024 * 1024)))  # 10 MB
ALLOWED_DOCUMENT_MIME_TYPES = ("application/pdf", "image/jpeg", "image/png")
SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes
