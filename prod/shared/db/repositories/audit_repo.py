"""Audit repository — CRUD for channel_reauth_audit_logs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, insert, text

from shared.db.connection import get_connection
from shared.db.models import channel_reauth_audit_logs


def create_reauth_audit(
    channel_id: int,
    status: str,
    initiated_at: datetime | None = None,
    metadata: dict[str, Any] | None = None,
) -> int | None:
    """Create an audit record. Returns new id."""
    initiated_at = initiated_at or datetime.now()
    metadata_json = json.dumps(metadata) if metadata else None
    stmt = insert(channel_reauth_audit_logs).values(
        channel_id=channel_id,
        initiated_at=initiated_at,
        status=status,
        metadata=metadata_json,
    )
    with get_connection() as conn:
        result = conn.execute(stmt)
        return result.lastrowid


def complete_reauth_audit(
    audit_id: int,
    status: str,
    completed_at: datetime | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Update an audit record with completion status."""
    completed_at = completed_at or datetime.now()
    metadata_json = json.dumps(metadata) if metadata else None
    sql = text(
        "UPDATE channel_reauth_audit_logs SET "
        "completed_at = :completed_at, "
        "status = :status, "
        "error_message = :error_message, "
        "metadata_ = COALESCE(:metadata, metadata_) "
        "WHERE id = :aid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "completed_at": completed_at,
            "status": status,
            "error_message": error_message,
            "metadata": metadata_json,
            "aid": audit_id,
        })
        return result.rowcount > 0


def get_recent_reauth_audits(
    channel_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve recent audit entries for a channel."""
    t = channel_reauth_audit_logs
    cols = [
        t.c.id, t.c.channel_id,
        t.c.initiated_at, t.c.completed_at,
        t.c.status, t.c.trigger_reason,
        t.c.error_message, t.c.error_code,
        t.c.metadata, t.c.created_at,
    ]
    stmt = (
        select(*cols)
        .where(t.c.channel_id == channel_id)
        .order_by(t.c.initiated_at.desc())
        .limit(limit)
    )
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row) -> dict[str, Any]:
    meta = None
    raw = row[8]
    if raw:
        try:
            meta = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": row[0],
        "channel_id": row[1],
        "initiated_at": row[2],
        "completed_at": row[3],
        "status": row[4],
        "trigger_reason": row[5],
        "error_message": row[6],
        "error_code": row[7],
        "metadata": meta,
        "created_at": row[9],
    }
