"""Task repository — CRUD for content_upload_queue_tasks."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, insert, text, func

from shared.db.connection import get_connection
from shared.db.models import content_upload_queue_tasks, platform_projects


def get_default_project_id() -> int | None:
    stmt = select(platform_projects.c.id).where(
        platform_projects.c.slug == "default"
    ).limit(1)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    return row[0] if row else None


def create_task(
    channel_id: int,
    source_file_path: str,
    title: str,
    scheduled_at: datetime,
    media_type: str = "video",
    thumbnail_path: str | None = None,
    description: str | None = None,
    keywords: str | None = None,
    post_comment: str | None = None,
    legacy_add_info: dict[str, Any] | None = None,
    project_id: int | None = None,
) -> int | None:
    """Insert a new upload task. Returns new id or None on error."""
    if project_id is None:
        project_id = get_default_project_id()
    if project_id is None:
        raise ValueError("No project_id provided and no default project found")

    add_info_json = json.dumps(legacy_add_info) if legacy_add_info else None
    stmt = insert(content_upload_queue_tasks).values(
        project_id=project_id,
        channel_id=channel_id,
        media_type=media_type,
        source_file_path=source_file_path,
        thumbnail_path=thumbnail_path,
        title=title,
        description=description,
        keywords=keywords,
        post_comment=post_comment,
        legacy_add_info=add_info_json,
        scheduled_at=scheduled_at,
    )
    with get_connection() as conn:
        result = conn.execute(stmt)
        return result.lastrowid


def get_task(task_id: int) -> dict[str, Any] | None:
    t = content_upload_queue_tasks
    cols = [
        t.c.id, t.c.channel_id, t.c.media_type, t.c.status,
        t.c.created_at, t.c.source_file_path, t.c.thumbnail_path,
        t.c.title, t.c.description, t.c.keywords, t.c.post_comment,
        t.c.legacy_add_info, t.c.scheduled_at, t.c.completed_at,
        t.c.upload_id, t.c.error_message, t.c.retry_count,
    ]
    stmt = select(*cols).where(t.c.id == task_id)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_pending_tasks(limit: int | None = None) -> list[dict[str, Any]]:
    """Get tasks with status=0 and scheduled_at <= NOW()."""
    t = content_upload_queue_tasks
    cols = [
        t.c.id, t.c.channel_id, t.c.media_type, t.c.status,
        t.c.created_at, t.c.source_file_path, t.c.thumbnail_path,
        t.c.title, t.c.description, t.c.keywords, t.c.post_comment,
        t.c.legacy_add_info, t.c.scheduled_at, t.c.completed_at,
        t.c.upload_id, t.c.error_message, t.c.retry_count,
    ]
    stmt = (
        select(*cols)
        .where(t.c.status == 0, t.c.scheduled_at <= func.now())
        .order_by(t.c.scheduled_at.asc())
    )
    if limit:
        stmt = stmt.limit(limit)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_tasks(
    status: int | None = None,
    channel_id: int | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    t = content_upload_queue_tasks
    cols = [
        t.c.id, t.c.channel_id, t.c.media_type, t.c.status,
        t.c.created_at, t.c.source_file_path, t.c.thumbnail_path,
        t.c.title, t.c.description, t.c.keywords, t.c.post_comment,
        t.c.legacy_add_info, t.c.scheduled_at, t.c.completed_at,
        t.c.upload_id, t.c.error_message, t.c.retry_count,
    ]
    stmt = select(*cols)
    if status is not None:
        stmt = stmt.where(t.c.status == status)
    if channel_id is not None:
        stmt = stmt.where(t.c.channel_id == channel_id)
    stmt = stmt.order_by(t.c.scheduled_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_token_related_failed_tasks(channel_id: int) -> list[dict[str, Any]]:
    """Get failed tasks with token-related error messages."""
    t = content_upload_queue_tasks
    cols = [
        t.c.id, t.c.channel_id, t.c.media_type, t.c.status,
        t.c.created_at, t.c.source_file_path, t.c.thumbnail_path,
        t.c.title, t.c.description, t.c.keywords, t.c.post_comment,
        t.c.legacy_add_info, t.c.scheduled_at, t.c.completed_at,
        t.c.upload_id, t.c.error_message, t.c.retry_count,
    ]
    patterns = [
        "%invalid_grant%",
        "%Token has been expired or revoked%",
        "%refresh token%invalid%",
        "%refresh token%revoked%",
        "%token expired%",
    ]
    stmt = (
        select(*cols)
        .where(
            t.c.status == 2,
            t.c.channel_id == channel_id,
            t.c.error_message.isnot(None),
        )
    )
    # OR across all token-error patterns
    from sqlalchemy import or_
    stmt = stmt.where(or_(*(t.c.error_message.like(p) for p in patterns)))
    stmt = stmt.order_by(t.c.scheduled_at.asc())
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_task_status(
    task_id: int,
    status: int,
    error_message: str | None = None,
    completed_at: datetime | None = None,
) -> bool:
    if completed_at is None and status == 1:
        completed_at = datetime.now()
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET status = :status, completed_at = :completed_at, error_message = :error_message "
        "WHERE id = :tid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "status": status,
            "completed_at": completed_at,
            "error_message": error_message,
            "tid": task_id,
        })
        return result.rowcount > 0


def mark_task_processing(task_id: int) -> bool:
    return update_task_status(task_id, 3)


def mark_task_completed(task_id: int, upload_id: str | None = None) -> bool:
    completed_at = datetime.now()
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET status = 1, completed_at = :completed_at, upload_id = :upload_id "
        "WHERE id = :tid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "completed_at": completed_at,
            "upload_id": upload_id,
            "tid": task_id,
        })
        return result.rowcount > 0


def mark_task_failed(task_id: int, error_message: str | None = None) -> bool:
    return update_task_status(task_id, 2, error_message=error_message)


def update_task_upload_id(task_id: int, upload_id: str) -> bool:
    sql = text(
        "UPDATE content_upload_queue_tasks SET upload_id = :uid WHERE id = :tid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"uid": upload_id, "tid": task_id})
        return result.rowcount > 0


def delete_task(task_id: int) -> bool:
    sql = text("DELETE FROM content_upload_queue_tasks WHERE id = :tid")
    with get_connection() as conn:
        result = conn.execute(sql, {"tid": task_id})
        return result.rowcount > 0


def _row_to_dict(row) -> dict[str, Any]:
    legacy_add_info = None
    raw = row[11]
    if raw:
        try:
            legacy_add_info = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "id": row[0],
        "channel_id": row[1],
        "media_type": row[2],
        "status": row[3],
        "created_at": row[4],
        "source_file_path": row[5],
        "thumbnail_path": row[6],
        "title": row[7],
        "description": row[8],
        "keywords": row[9],
        "post_comment": row[10],
        "legacy_add_info": legacy_add_info,
        "scheduled_at": row[12],
        "completed_at": row[13],
        "upload_id": row[14],
        "error_message": row[15],
        "retry_count": row[16],
    }
