"""
Supabase Storage Service — Sprint 2.
Person A: A-03 Secure Document Vault.

Handles private server-side document storage using the Supabase Storage REST API.
Operates using the service-role key to keep storage bucket operations private and
enforces that files are stored securely with temporary signed URLs only.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import httpx
from config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY,
    VERIFICATION_DOCUMENTS_BUCKET,
    SIGNED_URL_EXPIRY_SECONDS,
)


class StorageError(Exception):
    """Base exception for Supabase Storage operations."""
    pass


class StorageUploadError(StorageError):
    """Raised when file upload to Supabase Storage fails."""
    pass


class StorageSignedUrlError(StorageError):
    """Raised when generating a temporary signed URL fails."""
    pass


def _get_storage_headers(content_type: Optional[str] = None) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "apiKey": SUPABASE_SERVICE_KEY,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def ensure_bucket_exists(bucket_name: str = VERIFICATION_DOCUMENTS_BUCKET) -> bool:
    """
    Ensure that the designated private storage bucket exists.
    If not, create it as a private bucket (public=False).
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False

    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/bucket/{bucket_name}"
    headers = _get_storage_headers("application/json")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            return True

        if resp.status_code == 404:
            create_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/bucket"
            payload = {
                "id": bucket_name,
                "name": bucket_name,
                "public": False,
                "file_size_limit": 10485760,  # 10 MB
                "allowed_mime_types": ["application/pdf", "image/jpeg", "image/png"],
            }
            create_resp = await client.post(create_url, headers=headers, json=payload)
            if create_resp.status_code in (200, 201):
                return True
            raise StorageError(f"Failed to create bucket '{bucket_name}': {create_resp.text}")

        raise StorageError(f"Error checking bucket '{bucket_name}': {resp.status_code} {resp.text}")
