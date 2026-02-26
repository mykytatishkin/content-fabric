"""Channel repository - DB operations for platform_channels and platform_oauth_credentials."""

import json
from datetime import datetime

from app.core.database import execute_query, get_db_connection
from app.schemas.channel import ChannelCreate, ChannelCredentials


def list_oauth_credentials(enabled_only: bool = True) -> list[dict]:
    """List OAuth credentials for dropdown."""
    query = """
        SELECT id, name, COALESCE(description, '') as description, enabled
        FROM platform_oauth_credentials
        WHERE 1=1
    """
    if enabled_only:
        query += " AND enabled = 1"
    query += " ORDER BY name ASC"

    with get_db_connection() as conn:
        rows = execute_query(conn, query, fetch=True) or []
    return [
        {"id": r[0], "name": r[1], "description": r[2] or "", "enabled": bool(r[3])}
        for r in rows
    ]


# Keep old name as alias for backward compatibility in endpoints
list_google_consoles = list_oauth_credentials


def channel_exists_by_name(name: str) -> bool:
    """Check if channel with this name already exists."""
    query = "SELECT 1 FROM platform_channels WHERE name = %s LIMIT 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (name.strip(),), fetch=True)
    return bool(rows)


def channel_exists_by_channel_id(platform_channel_id: str) -> bool:
    """Check if channel with this platform_channel_id already exists."""
    query = "SELECT 1 FROM platform_channels WHERE platform_channel_id = %s LIMIT 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (platform_channel_id.strip(),), fetch=True)
    return bool(rows)


def get_console_by_id(console_id: int) -> dict | None:
    """Get OAuth credential by ID."""
    query = "SELECT id, name FROM platform_oauth_credentials WHERE id = %s AND enabled = 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (console_id,), fetch=True)
    if not rows:
        return None
    r = rows[0]
    return {"id": r[0], "name": r[1]}


def _get_default_project_id() -> int | None:
    """Get default project ID."""
    query = "SELECT id FROM platform_projects WHERE slug = 'default' LIMIT 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, fetch=True)
    return rows[0][0] if rows else None


def add_channel(data: ChannelCreate) -> int | None:
    """
    Add channel to DB. Returns new channel id or None on duplicate.
    """
    project_id = data.project_id or _get_default_project_id()
    if not project_id:
        raise ValueError("No project_id provided and no default project found")

    query = """
        INSERT INTO platform_channels
        (project_id, name, platform_channel_id, console_id, enabled)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (
        project_id,
        data.name.strip(),
        data.platform_channel_id.strip(),
        data.console_id,
        data.enabled,
    )

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            channel_id = cursor.lastrowid
            cursor.close()
            return channel_id
    except Exception as e:
        if hasattr(e, "errno") and e.errno == 1062:  # Duplicate entry
            return None
        raise


def add_account_credentials(channel_id: int, creds: ChannelCredentials) -> int:
    """
    Insert RPA auth credentials into platform_channel_login_credentials.
    Linked to platform_channels via channel_id FK.
    Returns the new row id.
    """
    query = """
        INSERT INTO platform_channel_login_credentials
        (channel_id, login_email, login_password, totp_secret, backup_codes,
         proxy_host, proxy_port, proxy_username, proxy_password, enabled)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
    """
    backup_codes_json = json.dumps(creds.backup_codes) if creds.backup_codes else None
    params = (
        channel_id,
        creds.login_email,
        creds.login_password,
        creds.totp_secret,
        backup_codes_json,
        creds.proxy_host,
        creds.proxy_port,
        creds.proxy_username,
        creds.proxy_password,
    )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        row_id = cursor.lastrowid
        cursor.close()
        return row_id


def list_channels(project_id: int | None = None) -> list[dict]:
    """List channels, optionally filtered by project_id."""
    if project_id:
        query = """
            SELECT id, name, platform_channel_id, console_id, enabled,
                   project_id, created_at, updated_at
            FROM platform_channels
            WHERE project_id = %s
            ORDER BY created_at DESC
        """
        params: tuple = (project_id,)
    else:
        query = """
            SELECT id, name, platform_channel_id, console_id, enabled,
                   project_id, created_at, updated_at
            FROM platform_channels
            ORDER BY created_at DESC
        """
        params = ()

    with get_db_connection() as conn:
        rows = execute_query(conn, query, params if params else None, fetch=True) or []

    return [
        {
            "id": r[0],
            "name": r[1],
            "platform_channel_id": r[2],
            "console_id": r[3],
            "enabled": bool(r[4]),
            "project_id": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows
    ]


def get_channel_by_id(channel_id: int) -> dict | None:
    """Get channel by ID."""
    query = """
        SELECT id, name, platform_channel_id, console_id, enabled,
               project_id, created_at, updated_at
        FROM platform_channels
        WHERE id = %s
    """
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (channel_id,), fetch=True)
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0],
        "name": r[1],
        "platform_channel_id": r[2],
        "console_id": r[3],
        "enabled": bool(r[4]),
        "project_id": r[5],
        "created_at": r[6],
        "updated_at": r[7],
    }
