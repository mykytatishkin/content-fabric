"""Channel repository - DB operations for youtube_channels and google_consoles."""

from datetime import datetime
from uuid import UUID

from app.core.database import execute_query, get_db_connection
from app.schemas.channel import ChannelCreate


def list_google_consoles(enabled_only: bool = True) -> list[dict]:
    """List Google consoles for dropdown."""
    query = """
        SELECT id, name, COALESCE(description, '') as description, enabled
        FROM google_consoles
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


def channel_exists_by_name(name: str) -> bool:
    """Check if channel with this name already exists."""
    query = "SELECT 1 FROM youtube_channels WHERE name = %s LIMIT 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (name.strip(),), fetch=True)
    return bool(rows)


def channel_exists_by_channel_id(channel_id: str) -> bool:
    """Check if channel with this YouTube channel_id already exists."""
    query = "SELECT 1 FROM youtube_channels WHERE channel_id = %s LIMIT 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (channel_id.strip(),), fetch=True)
    return bool(rows)


def get_console_by_id(console_id: int) -> dict | None:
    """Get console by ID."""
    query = "SELECT id, name FROM google_consoles WHERE id = %s AND enabled = 1"
    with get_db_connection() as conn:
        rows = execute_query(conn, query, (console_id,), fetch=True)
    if not rows:
        return None
    r = rows[0]
    return {"id": r[0], "name": r[1]}


def add_channel(data: ChannelCreate) -> int | None:
    """
    Add channel to DB. Returns new channel id or None on duplicate.
    Sets console_name from console_id for legacy worker compatibility.
    """
    console_name = None
    if data.console_id:
        console = get_console_by_id(data.console_id)
        if console:
            console_name = console["name"]

    query = """
        INSERT INTO youtube_channels
        (name, channel_id, console_id, console_name, enabled)
        VALUES (%s, %s, %s, %s, %s)
    """
    params = (
        data.name.strip(),
        data.channel_id.strip(),
        data.console_id,
        console_name,
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


def _row_to_channel_dict(r: tuple) -> dict:
    """Convert DB row to channel dict. Works with or without user_id column."""
    return {
        "id": r[0],
        "name": r[1],
        "channel_id": r[2],
        "console_id": r[3],
        "console_name": r[4],
        "enabled": bool(r[5]),
        "user_id": r[6] if len(r) > 6 else None,
        "created_at": r[7] if len(r) > 7 else r[6],
        "updated_at": r[8] if len(r) > 8 else r[7],
    }


def list_channels(user_id: UUID | None = None) -> list[dict]:
    """List channels, optionally filtered by user_id (when column exists)."""
    # Base columns - user_id optional (after migration)
    base_cols = "id, name, channel_id, console_id, console_name, enabled"
    try:
        if user_id:
            query = f"""
                SELECT {base_cols}, user_id, created_at, updated_at
                FROM youtube_channels
                WHERE user_id = %s OR user_id IS NULL
                ORDER BY created_at DESC
            """
            params: tuple = (str(user_id),)
        else:
            query = f"""
                SELECT {base_cols}, created_at, updated_at
                FROM youtube_channels
                ORDER BY created_at DESC
            """
            params = ()
        with get_db_connection() as conn:
            rows = execute_query(conn, query, params if params else None, fetch=True) or []
    except Exception:
        # user_id column might not exist - retry without
        query = f"""
            SELECT {base_cols}, created_at, updated_at
            FROM youtube_channels
            ORDER BY created_at DESC
        """
        with get_db_connection() as conn:
            rows = execute_query(conn, query, fetch=True) or []

    result = []
    for r in rows:
        d = {"id": r[0], "name": r[1], "channel_id": r[2], "console_id": r[3],
             "console_name": r[4], "enabled": bool(r[5]), "user_id": None}
        if len(r) == 9:
            d.update(created_at=r[7], updated_at=r[8])
        elif len(r) == 8:
            d.update(created_at=r[6], updated_at=r[7])
        result.append(d)
    return result


def get_channel_by_id(channel_id: int) -> dict | None:
    """Get channel by ID."""
    query = """
        SELECT id, name, channel_id, console_id, console_name, enabled,
               created_at, updated_at
        FROM youtube_channels
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
        "channel_id": r[2],
        "console_id": r[3],
        "console_name": r[4],
        "enabled": bool(r[5]),
        "user_id": None,
        "created_at": r[6],
        "updated_at": r[7],
    }
