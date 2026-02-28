"""Channel repository — CRUD for platform_channels."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select, insert, text

from shared.db.connection import get_connection
from shared.db.models import (
    platform_channels,
    platform_channel_login_credentials,
    platform_oauth_credentials,
    platform_projects,
)


def list_channels(project_id: int | None = None) -> list[dict[str, Any]]:
    cols = [
        platform_channels.c.id,
        platform_channels.c.name,
        platform_channels.c.platform_channel_id,
        platform_channels.c.console_id,
        platform_channels.c.enabled,
        platform_channels.c.project_id,
        platform_channels.c.created_at,
        platform_channels.c.updated_at,
    ]
    stmt = select(*cols).order_by(platform_channels.c.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(platform_channels.c.project_id == project_id)

    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()

    return [
        {
            "id": r[0], "name": r[1], "platform_channel_id": r[2],
            "console_id": r[3], "enabled": bool(r[4]), "project_id": r[5],
            "created_at": r[6], "updated_at": r[7],
        }
        for r in rows
    ]


def get_channel_by_id(channel_id: int) -> dict[str, Any] | None:
    cols = [
        platform_channels.c.id,
        platform_channels.c.name,
        platform_channels.c.platform_channel_id,
        platform_channels.c.console_id,
        platform_channels.c.enabled,
        platform_channels.c.project_id,
        platform_channels.c.access_token,
        platform_channels.c.refresh_token,
        platform_channels.c.token_expires_at,
        platform_channels.c.created_by,
        platform_channels.c.created_at,
        platform_channels.c.updated_at,
    ]
    stmt = select(*cols).where(platform_channels.c.id == channel_id)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "name": row[1], "platform_channel_id": row[2],
        "console_id": row[3], "enabled": bool(row[4]), "project_id": row[5],
        "access_token": row[6], "refresh_token": row[7],
        "token_expires_at": row[8], "created_by": row[9],
        "created_at": row[10], "updated_at": row[11],
    }


def get_channel_by_name(name: str) -> dict[str, Any] | None:
    cols = [
        platform_channels.c.id,
        platform_channels.c.name,
        platform_channels.c.platform_channel_id,
        platform_channels.c.console_id,
        platform_channels.c.enabled,
        platform_channels.c.access_token,
        platform_channels.c.refresh_token,
        platform_channels.c.token_expires_at,
    ]
    stmt = select(*cols).where(platform_channels.c.name == name)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "name": row[1], "platform_channel_id": row[2],
        "console_id": row[3], "enabled": bool(row[4]),
        "access_token": row[5], "refresh_token": row[6], "token_expires_at": row[7],
    }


def channel_exists_by_name(name: str) -> bool:
    stmt = select(platform_channels.c.id).where(
        platform_channels.c.name == name
    ).limit(1)
    with get_connection() as conn:
        return conn.execute(stmt).fetchone() is not None


def channel_exists_by_channel_id(platform_channel_id: str) -> bool:
    stmt = select(platform_channels.c.id).where(
        platform_channels.c.platform_channel_id == platform_channel_id
    ).limit(1)
    with get_connection() as conn:
        return conn.execute(stmt).fetchone() is not None


def get_all_channels(enabled_only: bool = False) -> list[dict[str, Any]]:
    cols = [
        platform_channels.c.id,
        platform_channels.c.name,
        platform_channels.c.platform_channel_id,
        platform_channels.c.console_id,
        platform_channels.c.access_token,
        platform_channels.c.refresh_token,
        platform_channels.c.token_expires_at,
        platform_channels.c.enabled,
        platform_channels.c.processing_status,
    ]
    stmt = select(*cols)
    if enabled_only:
        stmt = stmt.where(platform_channels.c.enabled == 1)
    stmt = stmt.order_by(platform_channels.c.name)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "platform_channel_id": r[2],
            "console_id": r[3], "access_token": r[4], "refresh_token": r[5],
            "token_expires_at": r[6], "enabled": bool(r[7]),
            "processing_status": r[8],
        }
        for r in rows
    ]


def get_default_project_id() -> int | None:
    stmt = select(platform_projects.c.id).where(
        platform_projects.c.slug == "default"
    ).limit(1)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    return row[0] if row else None


def add_channel(
    project_id: int,
    name: str,
    platform_channel_id: str,
    console_id: int | None = None,
    enabled: bool = True,
    created_by: int | None = None,
) -> int | None:
    """Insert channel. Returns new id or None on duplicate."""
    values = dict(
        project_id=project_id,
        name=name.strip(),
        platform_channel_id=platform_channel_id.strip(),
        console_id=console_id,
        enabled=int(enabled),
    )
    if created_by is not None:
        values["created_by"] = created_by
    stmt = insert(platform_channels).values(**values)
    try:
        with get_connection() as conn:
            result = conn.execute(stmt)
            return result.lastrowid
    except Exception as e:
        if "1062" in str(e):
            return None
        raise


def update_channel_tokens(
    channel_id: int,
    access_token: str,
    refresh_token: str | None = None,
    token_expires_at=None,
) -> bool:
    parts = ["access_token = :access_token"]
    params: dict[str, Any] = {"access_token": access_token, "cid": channel_id}
    if refresh_token is not None:
        parts.append("refresh_token = :refresh_token")
        params["refresh_token"] = refresh_token
    if token_expires_at is not None:
        parts.append("token_expires_at = :token_expires_at")
        params["token_expires_at"] = token_expires_at

    sql = f"UPDATE platform_channels SET {', '.join(parts)} WHERE id = :cid"
    with get_connection() as conn:
        result = conn.execute(text(sql), params)
        return result.rowcount > 0


def update_channel(channel_id: int, name: str | None = None, enabled: bool | None = None) -> bool:
    """Update channel fields."""
    parts = []
    params: dict[str, Any] = {"cid": channel_id}
    if name is not None:
        parts.append("name = :name")
        params["name"] = name
    if enabled is not None:
        parts.append("enabled = :enabled")
        params["enabled"] = int(enabled)
    if not parts:
        return False
    sql = text(f"UPDATE platform_channels SET {', '.join(parts)} WHERE id = :cid")
    with get_connection() as conn:
        result = conn.execute(sql, params)
        return result.rowcount > 0


def update_login_credentials(
    channel_id: int,
    login_email: str | None = None,
    login_password: str | None = None,
    totp_secret: str | None = None,
) -> bool:
    """Update existing login credentials for a channel."""
    parts = []
    params: dict[str, Any] = {"cid": channel_id}
    if login_email is not None:
        parts.append("login_email = :email")
        params["email"] = login_email
    if login_password is not None:
        parts.append("login_password = :pwd")
        params["pwd"] = login_password
    if totp_secret is not None:
        parts.append("totp_secret = :totp")
        params["totp"] = totp_secret
    if not parts:
        return False
    sql = text(
        f"UPDATE platform_channel_login_credentials SET {', '.join(parts)} WHERE channel_id = :cid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, params)
        return result.rowcount > 0


def delete_channel(channel_id: int) -> bool:
    """Delete channel and its login credentials."""
    with get_connection() as conn:
        conn.execute(text(
            "DELETE FROM platform_channel_login_credentials WHERE channel_id = :cid"
        ), {"cid": channel_id})
        result = conn.execute(text(
            "DELETE FROM platform_channels WHERE id = :cid"
        ), {"cid": channel_id})
        return result.rowcount > 0


def add_login_credentials(
    channel_id: int,
    login_email: str,
    login_password: str,
    totp_secret: str | None = None,
    backup_codes: list[str] | None = None,
    proxy_host: str | None = None,
    proxy_port: int | None = None,
    proxy_username: str | None = None,
    proxy_password: str | None = None,
) -> int:
    """Insert RPA login credentials. Returns new row id."""
    stmt = insert(platform_channel_login_credentials).values(
        channel_id=channel_id,
        login_email=login_email,
        login_password=login_password,
        totp_secret=totp_secret,
        backup_codes=json.dumps(backup_codes) if backup_codes else None,
        proxy_host=proxy_host,
        proxy_port=proxy_port,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
        enabled=1,
    )
    with get_connection() as conn:
        result = conn.execute(stmt)
        return result.lastrowid
