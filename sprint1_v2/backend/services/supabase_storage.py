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

        if resp.status_code in (404, 400) and ("not found" in resp.text.lower() or "nosuchbucket" in resp.text.lower() or resp.status_code == 404):
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


async def upload_file_to_storage(
    storage_path: str,
    file_bytes: bytes,
    content_type: str,
    bucket_name: str = VERIFICATION_DOCUMENTS_BUCKET,
) -> str:
    """
    Upload raw file bytes to the private Supabase Storage bucket.
    Uses x-upsert: false to guarantee that files are never overwritten.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise StorageUploadError("Supabase configuration is missing or incomplete")

    clean_path = storage_path.lstrip("/")
    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket_name}/{clean_path}"
    headers = _get_storage_headers(content_type)
    headers["x-upsert"] = "false"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, content=file_bytes)
        if resp.status_code in (200, 201):
            return clean_path

        raise StorageUploadError(
            f"Storage upload failed with status {resp.status_code}: {resp.text}"
        )


async def create_signed_url(
    storage_path: str,
    expires_in: int = SIGNED_URL_EXPIRY_SECONDS,
    bucket_name: str = VERIFICATION_DOCUMENTS_BUCKET,
) -> Dict[str, Any]:
    """
    Generate a short-lived signed URL (default 5 minutes / 300 seconds)
    for private document viewing. Never returns permanent public URLs.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise StorageSignedUrlError("Supabase configuration is missing or incomplete")

    clean_path = storage_path.lstrip("/")
    url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/sign/{bucket_name}/{clean_path}"
    headers = _get_storage_headers("application/json")
    payload = {"expiresIn": expires_in}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise StorageSignedUrlError(
                f"Failed to generate signed URL ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        relative_url = data.get("signedURL") or data.get("url")
        if not relative_url:
            raise StorageSignedUrlError("Signed URL response did not contain signedURL field")

        if relative_url.startswith("http://") or relative_url.startswith("https://"):
            full_signed_url = relative_url
        else:
            base_url = SUPABASE_URL.rstrip("/")
            if relative_url.startswith("/storage/v1"):
                full_signed_url = f"{base_url}{relative_url}"
            else:
                full_signed_url = f"{base_url}/storage/v1{relative_url}"

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return {
            "signed_url": full_signed_url,
            "expires_in": expires_in,
            "expires_at": expires_at.isoformat(),
        }

