"""Credential repository — CRUD for platform_channel_login_credentials."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, insert, text

from shared.db.connection import get_connection
from shared.db.models import platform_channel_login_credentials
from shared.db.utils import serialize_json, deserialize_json, truncate_error

logger = logging.getLogger(__name__)

_t = platform_channel_login_credentials
_CRED_COLS = [
    _t.c.id, _t.c.channel_id,
    _t.c.login_email, _t.c.login_password,
    _t.c.totp_secret, _t.c.backup_codes,
    _t.c.proxy_host, _t.c.proxy_port, _t.c.proxy_username, _t.c.proxy_password,
    _t.c.profile_path, _t.c.user_agent,
    _t.c.last_success_at, _t.c.last_attempt_at, _t.c.last_error,
    _t.c.enabled, _t.c.created_at, _t.c.updated_at,
]


def get_credentials(
    channel_id: int,
    include_disabled: bool = False,
) -> dict[str, Any] | None:
    """Get login credentials for a channel."""
    stmt = select(*_CRED_COLS).where(_t.c.channel_id == channel_id)
    if not include_disabled:
        stmt = stmt.where(_t.c.enabled == 1)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_credentials(
    channel_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List all login credentials, optionally filtered by channel_id."""
    stmt = select(*_CRED_COLS)
    if channel_id is not None:
        stmt = stmt.where(_t.c.channel_id == channel_id)
    stmt = stmt.order_by(_t.c.channel_id.asc())
    if limit:
        stmt = stmt.limit(limit)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def add_credentials(
    channel_id: int,
    login_email: str,
    login_password: str,
    totp_secret: str | None = None,
    backup_codes: list[str] | None = None,
    proxy_host: str | None = None,
    proxy_port: int | None = None,
    proxy_username: str | None = None,
    proxy_password: str | None = None,
    profile_path: str | None = None,
    user_agent: str | None = None,
    enabled: bool = True,
) -> int:
    """Insert login credentials. Returns new row id."""
    stmt = insert(platform_channel_login_credentials).values(
        channel_id=channel_id,
        login_email=login_email,
        login_password=login_password,
        totp_secret=totp_secret,
        backup_codes=serialize_json(backup_codes),
        proxy_host=proxy_host,
        proxy_port=proxy_port,
        proxy_username=proxy_username,
        proxy_password=proxy_password,
        profile_path=profile_path,
        user_agent=user_agent,
        enabled=int(enabled),
    )
    with get_connection() as conn:
        result = conn.execute(stmt)
        logger.info("Credentials added: id=%s channel=%s email=%s", result.lastrowid, channel_id, login_email)
        return result.lastrowid


def upsert_credentials(
    channel_id: int,
    login_email: str,
    login_password: str,
    totp_secret: str | None = None,
    backup_codes: list[str] | None = None,
    proxy_host: str | None = None,
    proxy_port: int | None = None,
    proxy_username: str | None = None,
    proxy_password: str | None = None,
    profile_path: str | None = None,
    user_agent: str | None = None,
    enabled: bool = True,
) -> bool:
    """Create or update login credentials (ON DUPLICATE KEY UPDATE)."""
    sql = text("""
        INSERT INTO platform_channel_login_credentials (
            channel_id, login_email, login_password,
            totp_secret, backup_codes,
            proxy_host, proxy_port, proxy_username, proxy_password,
            profile_path, user_agent, enabled
        )
        VALUES (
            :channel_id, :login_email, :login_password,
            :totp_secret, :backup_codes,
            :proxy_host, :proxy_port, :proxy_username, :proxy_password,
            :profile_path, :user_agent, :enabled
        )
        ON DUPLICATE KEY UPDATE
            login_email = VALUES(login_email),
            login_password = VALUES(login_password),
            totp_secret = VALUES(totp_secret),
            backup_codes = VALUES(backup_codes),
            proxy_host = VALUES(proxy_host),
            proxy_port = VALUES(proxy_port),
            proxy_username = VALUES(proxy_username),
            proxy_password = VALUES(proxy_password),
            profile_path = VALUES(profile_path),
            user_agent = VALUES(user_agent),
            enabled = VALUES(enabled),
            updated_at = CURRENT_TIMESTAMP
    """)
    with get_connection() as conn:
        conn.execute(sql, {
            "channel_id": channel_id,
            "login_email": login_email,
            "login_password": login_password,
            "totp_secret": totp_secret,
            "backup_codes": serialize_json(backup_codes),
            "proxy_host": proxy_host,
            "proxy_port": proxy_port,
            "proxy_username": proxy_username,
            "proxy_password": proxy_password,
            "profile_path": profile_path,
            "user_agent": user_agent,
            "enabled": int(enabled),
        })
        logger.info("Credentials upserted for channel %s email=%s", channel_id, login_email)
        return True


def disable_credentials(channel_id: int) -> bool:
    sql = text(
        "UPDATE platform_channel_login_credentials "
        "SET enabled = 0, updated_at = CURRENT_TIMESTAMP "
        "WHERE channel_id = :cid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"cid": channel_id})
        ok = result.rowcount > 0
        logger.info("Credentials disabled for channel %s (ok=%s)", channel_id, ok)
        return ok


def mark_attempt(
    channel_id: int,
    success: bool,
    error_message: str | None = None,
    attempt_time: datetime | None = None,
) -> bool:
    """Update credential metadata after an automation attempt."""
    attempt_time = attempt_time or datetime.now()
    sql = text(
        "UPDATE platform_channel_login_credentials SET "
        "last_attempt_at = :attempt_time, "
        "last_success_at = CASE WHEN :success THEN :success_time ELSE last_success_at END, "
        "last_error = :error_message, "
        "updated_at = CURRENT_TIMESTAMP "
        "WHERE channel_id = :cid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "attempt_time": attempt_time,
            "success": success,
            "success_time": attempt_time if success else None,
            "error_message": None if success else error_message,
            "cid": channel_id,
        })
        ok = result.rowcount > 0
        if success:
            logger.info("RPA attempt success for channel %s", channel_id)
        else:
            logger.warning("RPA attempt failed for channel %s: %s", channel_id, truncate_error(error_message))
        return ok


def update_totp_secret(
    channel_id: int,
    totp_secret: str | None,
    backup_codes: list[str] | None = None,
) -> bool:
    """Set or clear the TOTP secret for a channel's credentials."""
    sql = text(
        "UPDATE platform_channel_login_credentials "
        "SET totp_secret = :secret, backup_codes = :codes, updated_at = CURRENT_TIMESTAMP "
        "WHERE channel_id = :cid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "secret": totp_secret,
            "codes": serialize_json(backup_codes),
            "cid": channel_id,
        })
        ok = result.rowcount > 0
        logger.info("TOTP secret %s for channel %s (ok=%s)", "set" if totp_secret else "cleared", channel_id, ok)
        return ok


def update_profile_path(channel_id: int, profile_path: str) -> bool:
    sql = text(
        "UPDATE platform_channel_login_credentials "
        "SET profile_path = :path, updated_at = CURRENT_TIMESTAMP "
        "WHERE channel_id = :cid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"path": profile_path, "cid": channel_id})
        return result.rowcount > 0


def _row_to_dict(row) -> dict[str, Any]:
    return {
        "id": row[0],
        "channel_id": row[1],
        "login_email": row[2],
        "login_password": row[3],
        "totp_secret": row[4],
        "backup_codes": deserialize_json(row[5]),
        "proxy_host": row[6],
        "proxy_port": row[7],
        "proxy_username": row[8],
        "proxy_password": row[9],
        "profile_path": row[10],
        "user_agent": row[11],
        "last_success_at": row[12],
        "last_attempt_at": row[13],
        "last_error": row[14],
        "enabled": bool(row[15]),
        "created_at": row[16],
        "updated_at": row[17],
    }
