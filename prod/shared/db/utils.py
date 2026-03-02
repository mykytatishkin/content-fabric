"""Shared database utilities — JSON helpers, dynamic SQL builders."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

MAX_ERROR_LOG_LENGTH = 200

# MySQL duplicate-key error code
MYSQL_DUPLICATE_KEY = 1062


def serialize_json(obj: dict | list | None) -> str | None:
    """Safely serialize to JSON, return None if input is None/empty."""
    return json.dumps(obj) if obj else None


def deserialize_json(raw: str | dict | list | None, default=None):
    """Safely deserialize JSON with fallback."""
    if not raw:
        return default
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def is_duplicate_key_error(exc: Exception) -> bool:
    """Check if exception is a MySQL UNIQUE constraint violation."""
    return str(MYSQL_DUPLICATE_KEY) in str(exc)


def build_update(
    table: str,
    pk_column: str,
    pk_value: Any,
    **fields: Any,
) -> tuple[str, dict[str, Any]] | None:
    """Build a dynamic UPDATE query from non-None keyword arguments.

    Returns (sql_string, params_dict) or None if no fields to update.
    """
    parts: list[str] = []
    params: dict[str, Any] = {pk_column: pk_value}
    for key, value in fields.items():
        if value is not None:
            parts.append(f"{key} = :{key}")
            params[key] = value
    if not parts:
        return None
    sql = f"UPDATE {table} SET {', '.join(parts)} WHERE {pk_column} = :{pk_column}"
    return sql, params


def truncate_error(msg: str | None, length: int = MAX_ERROR_LOG_LENGTH) -> str | None:
    """Truncate error message for logging."""
    if not msg:
        return None
    return msg[:length] if len(msg) > length else msg
