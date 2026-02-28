"""User repository — CRUD for platform_users."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, insert, text

from shared.db.connection import get_connection
from shared.db.models import platform_users


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    t = platform_users
    cols = [
        t.c.id, t.c.uuid, t.c.username, t.c.email,
        t.c.password_hash, t.c.display_name, t.c.avatar_url,
        t.c.status, t.c.timezone, t.c.created_at, t.c.updated_at,
    ]
    stmt = select(*cols).where(t.c.id == user_id)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    t = platform_users
    cols = [
        t.c.id, t.c.uuid, t.c.username, t.c.email,
        t.c.password_hash, t.c.display_name, t.c.avatar_url,
        t.c.status, t.c.timezone, t.c.created_at, t.c.updated_at,
    ]
    stmt = select(*cols).where(t.c.email == email)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_user_by_username(username: str) -> dict[str, Any] | None:
    t = platform_users
    cols = [
        t.c.id, t.c.uuid, t.c.username, t.c.email,
        t.c.password_hash, t.c.display_name, t.c.avatar_url,
        t.c.status, t.c.timezone, t.c.created_at, t.c.updated_at,
    ]
    stmt = select(*cols).where(t.c.username == username)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


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
    sql = text(
        "UPDATE platform_users SET last_login_at = NOW() WHERE id = :uid"
    )
    with get_connection() as conn:
        conn.execute(sql, {"uid": user_id})


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
        "created_at": row[9],
        "updated_at": row[10],
    }
