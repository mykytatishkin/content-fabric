"""Console repository — CRUD for platform_oauth_credentials."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select, insert, text

from shared.db.connection import get_connection
from shared.db.models import platform_oauth_credentials, platform_projects

logger = logging.getLogger(__name__)


def get_default_project_id() -> int | None:
    stmt = select(platform_projects.c.id).where(
        platform_projects.c.slug == "default"
    ).limit(1)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    return row[0] if row else None


def list_consoles(enabled_only: bool = False) -> list[dict[str, Any]]:
    t = platform_oauth_credentials
    cols = [
        t.c.id, t.c.name, t.c.cloud_project_id, t.c.client_id,
        t.c.client_secret, t.c.credentials_file, t.c.redirect_uris,
        t.c.description, t.c.enabled, t.c.created_at, t.c.updated_at,
    ]
    stmt = select(*cols)
    if enabled_only:
        stmt = stmt.where(t.c.enabled == 1)
    stmt = stmt.order_by(t.c.name)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_consoles_brief(enabled_only: bool = True) -> list[dict[str, Any]]:
    """Lightweight listing for dropdowns (id, name, description, enabled)."""
    t = platform_oauth_credentials
    cols = [t.c.id, t.c.name, t.c.description, t.c.enabled]
    stmt = select(*cols)
    if enabled_only:
        stmt = stmt.where(t.c.enabled == 1)
    stmt = stmt.order_by(t.c.name)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [
        {"id": r[0], "name": r[1], "description": r[2] or "", "enabled": bool(r[3])}
        for r in rows
    ]


def get_console_by_id(console_id: int) -> dict[str, Any] | None:
    t = platform_oauth_credentials
    cols = [
        t.c.id, t.c.name, t.c.cloud_project_id, t.c.client_id,
        t.c.client_secret, t.c.credentials_file, t.c.redirect_uris,
        t.c.description, t.c.enabled, t.c.created_at, t.c.updated_at,
    ]
    stmt = select(*cols).where(t.c.id == console_id)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_console_by_name(name: str) -> dict[str, Any] | None:
    t = platform_oauth_credentials
    cols = [
        t.c.id, t.c.name, t.c.cloud_project_id, t.c.client_id,
        t.c.client_secret, t.c.credentials_file, t.c.redirect_uris,
        t.c.description, t.c.enabled, t.c.created_at, t.c.updated_at,
    ]
    stmt = select(*cols).where(t.c.name == name)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def add_console(
    name: str,
    client_id: str,
    client_secret: str,
    cloud_project_id: str | None = None,
    credentials_file: str | None = None,
    redirect_uris: list[str] | None = None,
    description: str | None = None,
    enabled: bool = True,
    project_id: int | None = None,
) -> int | None:
    """Insert OAuth credential. Returns new id or None on duplicate."""
    if project_id is None:
        project_id = get_default_project_id()
    if project_id is None:
        raise ValueError("No project_id provided and no default project found")

    redirect_uris_json = json.dumps(redirect_uris) if redirect_uris else None
    stmt = insert(platform_oauth_credentials).values(
        project_id=project_id,
        name=name,
        cloud_project_id=cloud_project_id,
        client_id=client_id,
        client_secret=client_secret,
        credentials_file=credentials_file,
        redirect_uris=redirect_uris_json,
        description=description,
        enabled=int(enabled),
    )
    try:
        with get_connection() as conn:
            result = conn.execute(stmt)
            logger.info("Console added: id=%s name=%s project=%s", result.lastrowid, name, cloud_project_id)
            return result.lastrowid
    except Exception as e:
        if "1062" in str(e):
            logger.warning("Duplicate console: name=%s", name)
            return None
        raise


def update_console(
    console_id: int,
    client_id: str | None = None,
    client_secret: str | None = None,
    credentials_file: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
) -> bool:
    parts: list[str] = []
    params: dict[str, Any] = {"cid": console_id}
    if client_id is not None:
        parts.append("client_id = :client_id")
        params["client_id"] = client_id
    if client_secret is not None:
        parts.append("client_secret = :client_secret")
        params["client_secret"] = client_secret
    if credentials_file is not None:
        parts.append("credentials_file = :credentials_file")
        params["credentials_file"] = credentials_file
    if description is not None:
        parts.append("description = :description")
        params["description"] = description
    if enabled is not None:
        parts.append("enabled = :enabled")
        params["enabled"] = int(enabled)
    if not parts:
        return False

    sql = f"UPDATE platform_oauth_credentials SET {', '.join(parts)} WHERE id = :cid"
    with get_connection() as conn:
        result = conn.execute(text(sql), params)
        return result.rowcount > 0


def delete_console(console_id: int) -> bool:
    sql = text("DELETE FROM platform_oauth_credentials WHERE id = :cid")
    with get_connection() as conn:
        result = conn.execute(sql, {"cid": console_id})
        ok = result.rowcount > 0
        logger.info("Console %s deleted (ok=%s)", console_id, ok)
        return ok


def _row_to_dict(row) -> dict[str, Any]:
    redirect_uris = None
    raw = row[6]
    if raw:
        try:
            redirect_uris = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": row[0],
        "name": row[1],
        "cloud_project_id": row[2],
        "client_id": row[3],
        "client_secret": row[4],
        "credentials_file": row[5],
        "redirect_uris": redirect_uris,
        "description": row[7],
        "enabled": bool(row[8]),
        "created_at": row[9],
        "updated_at": row[10],
    }
