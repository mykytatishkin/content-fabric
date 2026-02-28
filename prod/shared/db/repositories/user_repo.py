"""User repository — CRUD for platform_users."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, insert, text

from shared.db.connection import get_connection
from shared.db.models import platform_users

_USER_COLS = [
    platform_users.c.id,
    platform_users.c.uuid,
    platform_users.c.username,
    platform_users.c.email,
    platform_users.c.password_hash,
    platform_users.c.display_name,
    platform_users.c.avatar_url,
    platform_users.c.status,
    platform_users.c.timezone,
    platform_users.c.totp_secret,
    platform_users.c.totp_enabled,
    platform_users.c.totp_backup_codes,
    platform_users.c.created_at,
    platform_users.c.updated_at,
]


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    stmt = select(*_USER_COLS).where(platform_users.c.id == user_id)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    return _row_to_dict(row) if row else None


def get_user_by_email(email: str) -> dict[str, Any] | None:
    stmt = select(*_USER_COLS).where(platform_users.c.email == email)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    return _row_to_dict(row) if row else None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    stmt = select(*_USER_COLS).where(platform_users.c.username == username)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    return _row_to_dict(row) if row else None


def create_user(
    uuid: str,
    username: str,
    email: str,
    password_hash: str,
    auth_key: str,
    display_name: str | None = None,
) -> int:
    """Insert a new user. Returns user id."""
    stmt = insert(platform_users).values(
        uuid=uuid,
        username=username,
        email=email,
        password_hash=password_hash,
        auth_key=auth_key,
        display_name=display_name or username,
    )
    with get_connection() as conn:
        result = conn.execute(stmt)
        return result.lastrowid


def update_last_login(user_id: int) -> None:
    sql = text("UPDATE platform_users SET last_login_at = NOW() WHERE id = :uid")
    with get_connection() as conn:
        conn.execute(sql, {"uid": user_id})


def set_totp_secret(user_id: int, secret: str) -> None:
    """Store the TOTP secret (before user confirms setup)."""
    sql = text("UPDATE platform_users SET totp_secret = :secret WHERE id = :uid")
    with get_connection() as conn:
        conn.execute(sql, {"secret": secret, "uid": user_id})


def enable_totp(user_id: int, backup_codes: list[str]) -> None:
    """Activate 2FA after user confirms with a valid TOTP code."""
    import json
    sql = text(
        "UPDATE platform_users SET totp_enabled = 1, totp_backup_codes = :codes WHERE id = :uid"
    )
    with get_connection() as conn:
        conn.execute(sql, {"codes": json.dumps(backup_codes), "uid": user_id})


def disable_totp(user_id: int) -> None:
    """Turn off 2FA."""
    sql = text(
        "UPDATE platform_users SET totp_enabled = 0, totp_secret = NULL, totp_backup_codes = NULL WHERE id = :uid"
    )
    with get_connection() as conn:
        conn.execute(sql, {"uid": user_id})


def consume_backup_code(user_id: int, code: str) -> bool:
    """Use a one-time backup code. Returns True if code was valid."""
    import json
    user = get_user_by_id(user_id)
    if not user:
        return False
    codes: list[str] = user.get("totp_backup_codes") or []
    if isinstance(codes, str):
        codes = json.loads(codes)
    if code not in codes:
        return False
    codes.remove(code)
    sql = text("UPDATE platform_users SET totp_backup_codes = :codes WHERE id = :uid")
    with get_connection() as conn:
        conn.execute(sql, {"codes": json.dumps(codes), "uid": user_id})
    return True


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row[0],
        "uuid": row[1],
        "username": row[2],
        "email": row[3],
        "password_hash": row[4],
        "display_name": row[5],
        "avatar_url": row[6],
        "status": row[7],
        "timezone": row[8],
        "totp_secret": row[9],
        "totp_enabled": bool(row[10]),
        "totp_backup_codes": row[11],
        "created_at": row[12],
        "updated_at": row[13],
    }
