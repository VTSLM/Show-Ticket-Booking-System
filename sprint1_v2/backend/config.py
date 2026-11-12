import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or "postgresql://postgres.nvgghebapzhxzrwunwrj:IT314SoftwareEngineering@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://nvgghebapzhxzrwunwrj.supabase.co"
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im52Z2doZWJhcHpoeHpyd3Vud3JqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MTAzOTI0MywiZXhwIjoyMTA2NjE1MjQzfQ.H2ieFx7ERXeZ2ryU15UAjpVb6EhsWwkuz1PVIVn_eeg"
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im52Z2doZWJhcHpoeHpyd3Vud3JqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTEwMzkyNDMsImV4cCI6MjEwNjYxNTI0M30.c9MND0-buyRcsIwhTaM-2Lze25woQMBVirCYfONC1I4"
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
