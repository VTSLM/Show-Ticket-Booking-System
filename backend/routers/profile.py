"""
Edit profile info (Sprint 2, Tirth).

GET    /api/profile        → the logged-in user's profile
PATCH  /api/profile        → update name, phone, birthdate and/or bio (only the fields sent)
POST   /api/profile/photo  → upload / replace profile photo (JPG, PNG, WebP, max 2 MB)
DELETE /api/profile/photo  → remove profile photo

Email is not editable here because it is the Firebase login identity.
"""
import re
from datetime import date
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from database import get_conn
from dependencies import get_current_user
from services.avatar_storage import (
    MAX_UPLOAD_BYTES, AvatarError, delete_avatar, process_image, upload_avatar,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")
PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")      # Indian mobile number, 10 digits
BIO_MAX = 300


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    phone: Optional[str] = None
    birthdate: Optional[date] = None
    bio: Optional[str] = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            raise ValueError("Name cannot be empty")
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if not NAME_PATTERN.match(v):
            raise ValueError("Name can only contain letters, spaces, dots, apostrophes and hyphens")
        return v

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        digits = re.sub(r"[\s\-]", "", v)
        if digits.startswith("+91"):
            digits = digits[3:]
        if digits == "":
            return None                       # clearing the phone number is allowed
        if not PHONE_PATTERN.match(digits):
            raise ValueError("Enter a valid 10-digit Indian mobile number")
        return digits

    @field_validator("birthdate")
    @classmethod
    def valid_birthdate(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            raise ValueError("Birthdate cannot be empty")
        today = date.today()
        if v > today:
            raise ValueError("Birthdate cannot be in the future")
        if v.year < today.year - 120:
            raise ValueError("Please enter a valid birthdate")
        return v

    @field_validator("bio")
    @classmethod
    def valid_bio(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if len(v) > BIO_MAX:
            raise ValueError(f"Bio must be at most {BIO_MAX} characters")
        return v or None                      # empty bio is stored as NULL


async def _load_profile(conn: asyncpg.Connection, user_id) -> dict:
    row = await conn.fetchrow(
        """SELECT u.id, u.name, u.email, u.phone, u.birthdate, u.bio, u.avatar_url, u.status, u.created_at,
                  array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
           FROM users u
           LEFT JOIN user_roles ur ON ur.user_id = u.id
           LEFT JOIN roles r ON r.id = ur.role_id
           WHERE u.id = $1
           GROUP BY u.id""",
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile = dict(row)
    profile["roles"] = list(profile["roles"]) if profile["roles"] else []
    return profile


@router.get("")
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    return await _load_profile(conn, current_user["id"])


@router.patch("")
async def update_my_profile(
    body: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    # Only update the fields the client actually sent
    updates = {field: getattr(body, field) for field in body.model_fields_set}
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")

    columns = list(updates)                    # fixed whitelist from the model above
    set_clause = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(columns))
    await conn.execute(
        f"UPDATE users SET {set_clause}, updated_at = now() WHERE id = $1",
        current_user["id"], *[updates[c] for c in columns],
    )
    return await _load_profile(conn, current_user["id"])


@router.post("/photo")
async def upload_my_photo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)       # never read more than the limit
    try:
        jpeg = process_image(data)
        new_url = await upload_avatar(str(current_user["id"]), jpeg)
    except AvatarError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    old_url = current_user.get("avatar_url")
    await conn.execute(
        "UPDATE users SET avatar_url = $2, updated_at = now() WHERE id = $1",
        current_user["id"], new_url,
    )
    await delete_avatar(old_url)                      # remove the previous photo file
    return await _load_profile(conn, current_user["id"])


@router.delete("/photo")
async def remove_my_photo(
    current_user: dict = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_conn),
):
    old_url = current_user.get("avatar_url")
    await conn.execute(
        "UPDATE users SET avatar_url = NULL, updated_at = now() WHERE id = $1",
        current_user["id"],
    )
    await delete_avatar(old_url)
    return await _load_profile(conn, current_user["id"])
