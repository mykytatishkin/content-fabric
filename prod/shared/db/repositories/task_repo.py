"""Task repository — CRUD for content_upload_queue_tasks."""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, insert, text, func, or_

from shared.db.connection import get_connection
from shared.db.models import TaskStatus, content_upload_queue_tasks, platform_projects
from shared.db.utils import serialize_json, deserialize_json, truncate_error

logger = logging.getLogger(__name__)


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
    created_by: int | None = None,
) -> int | None:
    """Insert a new upload task. Returns new id or None on error."""
    if project_id is None:
        project_id = get_default_project_id()
    if project_id is None:
        raise ValueError("No project_id provided and no default project found")

    add_info_json = serialize_json(legacy_add_info)
    values = dict(
        uuid=str(_uuid.uuid4()),
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
    if created_by is not None:
        values["created_by"] = created_by
    stmt = insert(content_upload_queue_tasks).values(**values)
    with get_connection() as conn:
        result = conn.execute(stmt)
        logger.info("Task inserted: id=%s channel=%s created_by=%s", result.lastrowid, channel_id, created_by)
        return result.lastrowid


def _task_cols():
    t = content_upload_queue_tasks
    return [
        t.c.id, t.c.channel_id, t.c.media_type, t.c.status,
        t.c.created_at, t.c.source_file_path, t.c.thumbnail_path,
        t.c.title, t.c.description, t.c.keywords, t.c.post_comment,
        t.c.legacy_add_info, t.c.scheduled_at, t.c.completed_at,
        t.c.upload_id, t.c.error_message, t.c.retry_count,
        t.c.created_by, t.c.uuid,
    ]


def get_task(task_id: int) -> dict[str, Any] | None:
    t = content_upload_queue_tasks
    stmt = select(*_task_cols()).where(t.c.id == task_id)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_task_by_uuid(uuid: str) -> dict[str, Any] | None:
    t = content_upload_queue_tasks
    stmt = select(*_task_cols()).where(t.c.uuid == uuid)
    with get_connection() as conn:
        row = conn.execute(stmt).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_pending_tasks(limit: int | None = None) -> list[dict[str, Any]]:
    """Get tasks with status=0 and scheduled_at <= NOW()."""
    t = content_upload_queue_tasks
    stmt = (
        select(*_task_cols())
        .where(t.c.status == TaskStatus.PENDING.value, t.c.scheduled_at <= func.now())
        .order_by(t.c.scheduled_at.asc())
    )
    if limit:
        stmt = stmt.limit(limit)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_all_tasks(
    status: int | None = None,
    statuses: list[int] | None = None,
    channel_id: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    created_by: int | None = None,
) -> list[dict[str, Any]]:
    t = content_upload_queue_tasks
    stmt = select(*_task_cols())
    if created_by is not None:
        stmt = stmt.where(t.c.created_by == created_by)
    if status is not None:
        stmt = stmt.where(t.c.status == status)
    elif statuses:
        stmt = stmt.where(t.c.status.in_(statuses))
    if channel_id is not None:
        stmt = stmt.where(t.c.channel_id == channel_id)
    if date_from is not None:
        stmt = stmt.where(t.c.scheduled_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(t.c.scheduled_at <= date_to)
    stmt = stmt.order_by(t.c.scheduled_at.desc())
    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    with get_connection() as conn:
        rows = conn.execute(stmt).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_token_related_failed_tasks(channel_id: int) -> list[dict[str, Any]]:
    """Get failed tasks with token-related error messages."""
    t = content_upload_queue_tasks
    patterns = [
        "%invalid_grant%",
        "%Token has been expired or revoked%",
        "%refresh token%invalid%",
        "%refresh token%revoked%",
        "%token expired%",
    ]
    stmt = (
        select(*_task_cols())
        .where(
            t.c.status == TaskStatus.FAILED.value,
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
    if completed_at is None and status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        completed_at = datetime.now()
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET status = :status, completed_at = :completed_at, error_message = :error_message "
        "WHERE id = :tid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "status": int(status),
            "completed_at": completed_at,
            "error_message": error_message,
            "tid": task_id,
        })
        ok = result.rowcount > 0
        logger.info("Task %s status → %s (ok=%s, error=%s)", task_id, status, ok, truncate_error(error_message))
        return ok


def mark_task_processing(task_id: int) -> bool:
    return update_task_status(task_id, TaskStatus.PROCESSING.value)


def mark_task_completed(task_id: int, upload_id: str | None = None) -> bool:
    logger.info("Marking task %s completed (upload_id=%s)", task_id, upload_id)
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
    logger.warning("Marking task %s failed: %s", task_id, truncate_error(error_message) or "no message")
    return update_task_status(task_id, TaskStatus.FAILED.value, error_message=error_message)


def update_task_upload_id(task_id: int, upload_id: str) -> bool:
    sql = text(
        "UPDATE content_upload_queue_tasks SET upload_id = :uid WHERE id = :tid"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"uid": upload_id, "tid": task_id})
        return result.rowcount > 0


def retry_task(task_id: int) -> bool:
    """Reset a failed/cancelled task back to pending."""
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET status = 0, error_message = NULL, retry_count = retry_count + 1 "
        "WHERE id = :tid AND status IN (2, 4)"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"tid": task_id})
        return result.rowcount > 0


def retry_all_failed_by_channel(channel_id: int) -> int:
    """Reset all failed/cancelled tasks for a channel back to pending."""
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET status = 0, error_message = NULL, retry_count = retry_count + 1 "
        "WHERE channel_id = :cid AND status IN (2, 4)"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"cid": channel_id})
        return result.rowcount


def cancel_task(task_id: int) -> bool:
    """Cancel a task (set status=4). Only allowed if status in (0, 3)."""
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET status = 4 WHERE id = :tid AND status IN (0, 3)"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"tid": task_id})
        return result.rowcount > 0


def update_task_scheduled_at(task_id: int, scheduled_at: datetime) -> bool:
    """Reschedule a task. Only allowed if status in (0, 3)."""
    sql = text(
        "UPDATE content_upload_queue_tasks "
        "SET scheduled_at = :scheduled_at WHERE id = :tid AND status IN (0, 3)"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"scheduled_at": scheduled_at, "tid": task_id})
        return result.rowcount > 0


def create_tasks_batch(tasks: list[dict[str, Any]]) -> list[int]:
    """Create multiple tasks in a single transaction. Returns list of IDs."""
    project_id = get_default_project_id()
    if project_id is None:
        raise ValueError("No default project found")

    ids: list[int] = []
    from shared.db.connection import get_engine
    with get_engine().begin() as conn:
        for t in tasks:
            add_info = serialize_json(t.get("legacy_add_info"))
            values = dict(
                uuid=str(_uuid.uuid4()),
                project_id=project_id,
                channel_id=t["channel_id"],
                media_type=t.get("media_type", "video"),
                source_file_path=t["source_file_path"],
                thumbnail_path=t.get("thumbnail_path"),
                title=t["title"],
                description=t.get("description"),
                keywords=t.get("keywords"),
                post_comment=t.get("post_comment"),
                legacy_add_info=add_info,
                scheduled_at=t["scheduled_at"],
            )
            if t.get("created_by") is not None:
                values["created_by"] = t["created_by"]
            stmt = insert(content_upload_queue_tasks).values(**values)
            result = conn.execute(stmt)
            ids.append(result.lastrowid)
    return ids


def delete_task(task_id: int) -> bool:
    sql = text("DELETE FROM content_upload_queue_tasks WHERE id = :tid")
    with get_connection() as conn:
        result = conn.execute(sql, {"tid": task_id})
        return result.rowcount > 0


def _row_to_dict(row) -> dict[str, Any]:
    d = {
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
        "legacy_add_info": deserialize_json(row[11]),
        "scheduled_at": row[12],
        "completed_at": row[13],
        "upload_id": row[14],
        "error_message": row[15],
        "retry_count": row[16],
    }
    if len(row) > 17:
        d["created_by"] = row[17]
    if len(row) > 18:
        d["uuid"] = row[18]
    return d
