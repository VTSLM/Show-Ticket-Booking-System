"""
Admin user management (#138): list users, change roles, block and unblock.

Every change is written to ``admin_audit_log`` in the same transaction, with
the acting admin, the target user, what changed and the admin's reason.

Rules:
  * Only the manager and admin roles can be added or removed here. Customers keep
    their customer role; a user left with no role gets the customer role back.
  * Admins cannot change their own roles or status, so nobody locks themselves out.
  * The last active admin cannot lose the admin role.
  * Blocking takes effect on the user's next request (``get_current_user`` refuses
    blocked accounts); their Firebase sessions are also revoked, best effort.
"""
import asyncio
import json
import logging
from typing import Optional

import asyncpg
from fastapi import HTTPException

logger = logging.getLogger("uvicorn.error")

MANAGEABLE_ROLES = ("manager", "admin")
ACCOUNT_STATUSES = ("active", "blocked")
AUDIT_ENTRIES_SHOWN = 20


def _like_pattern(text: str) -> str:
    """ILIKE pattern that matches ``text`` literally anywhere in the value."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _user_out(row) -> dict:
    user = dict(row)
    user.pop("firebase_uid", None)  # internal; never sent to the browser
    user["id"] = str(user["id"])
    user["status"] = str(user["status"])
    user["roles"] = sorted(user.get("roles") or [])
    return user


async def list_users(
    conn: asyncpg.Connection,
    q: Optional[str],
    role: Optional[str],
    status: Optional[str],
    page: int,
    page_size: int,
) -> dict:
    pattern = _like_pattern(q.strip()) if q and q.strip() else None
    filters = """
        WHERE ($1::text IS NULL OR u.name ILIKE $1 OR u.email ILIKE $1)
          AND ($2::text IS NULL OR u.status::text = $2)
          AND ($3::text IS NULL OR EXISTS (
                SELECT 1 FROM user_roles fr JOIN roles fro ON fro.id = fr.role_id
                WHERE fr.user_id = u.id AND fro.code = $3))
    """
    total = await conn.fetchval(f"SELECT COUNT(*) FROM users u {filters}", pattern, status, role)
    rows = await conn.fetch(
        f"""SELECT u.id, u.name, u.email, u.phone, u.status, u.created_at,
                   array_agg(r.code) FILTER (WHERE r.code IS NOT NULL) AS roles
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            LEFT JOIN roles r ON r.id = ur.role_id
            {filters}
            GROUP BY u.id
            ORDER BY u.created_at DESC, u.id
            LIMIT $4 OFFSET $5""",
        pattern, status, role, page_size, (page - 1) * page_size,
    )
    return {
        "users": [_user_out(r) for r in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


async def _fetch_user(conn: asyncpg.Connection, user_id: str, lock: bool = False):
    row = await conn.fetchrow(
        f"""SELECT u.id, u.firebase_uid, u.name, u.email, u.phone, u.status, u.created_at
            FROM users u WHERE u.id = $1::uuid {"FOR UPDATE" if lock else ""}""",
        user_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    roles = await conn.fetch(
        """SELECT r.code FROM user_roles ur JOIN roles r ON r.id = ur.role_id
           WHERE ur.user_id = $1::uuid""",
        user_id,
    )
    user = dict(row)
    user["roles"] = [r["code"] for r in roles]
    return user


async def get_user(conn: asyncpg.Connection, user_id: str) -> dict:
    user = await _fetch_user(conn, user_id)
    history = await conn.fetch(
        """SELECT l.id, l.action, l.details, l.reason, l.created_at,
                  a.name AS admin_name, a.email AS admin_email
           FROM admin_audit_log l
           LEFT JOIN users a ON a.id = l.admin_id
           WHERE l.target_user_id = $1::uuid
           ORDER BY l.created_at DESC
           LIMIT $2""",
        user_id, AUDIT_ENTRIES_SHOWN,
    )
    out = _user_out(user)
    out["history"] = [
        {
            **dict(h),
            "id": str(h["id"]),
            "details": json.loads(h["details"]) if isinstance(h["details"], str) else h["details"],
        }
        for h in history
    ]
    return out


async def write_audit(
    conn: asyncpg.Connection,
    admin_id: str,
    target_user_id: str,
    action: str,
    details: dict,
    reason: Optional[str],
) -> None:
    await conn.execute(
        """INSERT INTO admin_audit_log (admin_id, target_user_id, action, details, reason)
           VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, $5)""",
        str(admin_id), str(target_user_id), action, json.dumps(details), reason,
    )


def _refuse_self(admin: dict, user_id: str, what: str) -> None:
    if str(admin["id"]) == str(user_id):
        raise HTTPException(status_code=400, detail=f"You cannot change your own {what}")


async def change_role(
    conn: asyncpg.Connection, admin: dict, user_id: str, role: str, action: str, reason: str
) -> dict:
    if role not in MANAGEABLE_ROLES:
        raise HTTPException(status_code=400, detail="Only the manager and admin roles can be changed")
    _refuse_self(admin, user_id, "roles")

    async with conn.transaction():
        user = await _fetch_user(conn, user_id, lock=True)
        has_role = role in user["roles"]

        if action == "add":
            if has_role:
                raise HTTPException(status_code=409, detail=f"User already has the {role} role")
            await conn.execute(
                """INSERT INTO user_roles (user_id, role_id)
                   SELECT $1::uuid, id FROM roles WHERE code = $2
                   ON CONFLICT DO NOTHING""",
                user_id, role,
            )
        else:
            if not has_role:
                raise HTTPException(status_code=409, detail=f"User does not have the {role} role")
            if role == "admin":
                other_admins = await conn.fetchval(
                    """SELECT COUNT(*) FROM users u
                       JOIN user_roles ur ON ur.user_id = u.id
                       JOIN roles r ON r.id = ur.role_id
                       WHERE r.code = 'admin' AND u.status = 'active' AND u.id <> $1::uuid""",
                    user_id,
                )
                if not other_admins:
                    raise HTTPException(status_code=409, detail="The last active admin cannot lose the admin role")
            await conn.execute(
                """DELETE FROM user_roles
                   WHERE user_id = $1::uuid
                     AND role_id = (SELECT id FROM roles WHERE code = $2)""",
                user_id, role,
            )
            # Nobody is left without a role: fall back to customer
            if len(user["roles"]) == 1:
                await conn.execute(
                    """INSERT INTO user_roles (user_id, role_id)
                       SELECT $1::uuid, id FROM roles WHERE code = 'customer'
                       ON CONFLICT DO NOTHING""",
                    user_id,
                )

        await conn.execute("UPDATE users SET updated_at = now() WHERE id = $1::uuid", user_id)
        await write_audit(
            conn, admin["id"], user_id,
            "role_added" if action == "add" else "role_removed",
            {"role": role}, reason,
        )
        updated = await _fetch_user(conn, user_id)

    return _user_out(updated)


async def change_status(
    conn: asyncpg.Connection, admin: dict, user_id: str, status: str, reason: str
) -> tuple[dict, Optional[str]]:
    """Returns the updated user and, when the user was blocked, their Firebase uid
    so the caller can revoke their sessions after the response."""
    if status not in ACCOUNT_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be active or blocked")
    _refuse_self(admin, user_id, "status")

    async with conn.transaction():
        user = await _fetch_user(conn, user_id, lock=True)
        previous = str(user["status"])
        if previous == status:
            raise HTTPException(status_code=409, detail=f"User is already {status}")
        await conn.execute(
            "UPDATE users SET status = $2, updated_at = now() WHERE id = $1::uuid",
            user_id, status,
        )
        await write_audit(
            conn, admin["id"], user_id, "status_changed",
            {"from": previous, "to": status}, reason,
        )
        updated = await _fetch_user(conn, user_id)

    firebase_uid = updated["firebase_uid"] if status == "blocked" else None
    return _user_out(updated), firebase_uid


async def revoke_sessions(firebase_uid: str) -> None:
    """Sign a blocked user out of Firebase everywhere. Best effort: the API already
    refuses blocked accounts, so a failure here is only logged."""
    from firebase_admin_setup import revoke_refresh_tokens

    try:
        await asyncio.to_thread(revoke_refresh_tokens, firebase_uid)
    except Exception as exc:
        logger.warning("Could not revoke Firebase sessions for a blocked user: %s", exc)
