"""Task management endpoints — creates tasks in DB, scheduler enqueues to Redis."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.audit import log as audit_log
from app.schemas.task import TaskBatchCreate, TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from shared.db.models import TaskStatus
from shared.db.repositories import task_repo

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(body: TaskCreate, user: dict = Depends(get_current_user)):
    """Create a new upload task. Scheduler picks it up and enqueues to Redis."""
    task_id = task_repo.create_task(
        channel_id=body.channel_id,
        source_file_path=body.source_file_path,
        title=body.title,
        scheduled_at=body.scheduled_at,
        media_type=body.media_type,
        thumbnail_path=body.thumbnail_path,
        description=body.description,
        keywords=body.keywords,
        post_comment=body.post_comment,
        legacy_add_info=body.legacy_add_info,
    )
    if task_id is None:
        raise HTTPException(status_code=500, detail="Failed to create task")

    task = task_repo.get_task(task_id)
    audit_log("task.create", actor_id=user.get("id"), entity_type="task", entity_id=task_id,
              metadata={"channel_id": body.channel_id, "title": body.title})
    return TaskResponse(**task)


@router.post("/batch", response_model=TaskListResponse, status_code=status.HTTP_201_CREATED)
async def create_tasks_batch(body: TaskBatchCreate, user: dict = Depends(get_current_user)):
    """Create multiple tasks in a single transaction."""
    if len(body.tasks) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 tasks per batch")

    task_dicts = [t.model_dump() for t in body.tasks]
    ids = task_repo.create_tasks_batch(task_dicts)

    tasks = [task_repo.get_task(tid) for tid in ids]
    tasks = [t for t in tasks if t is not None]

    audit_log("task.batch_create", actor_id=user.get("id"), entity_type="task",
              metadata={"count": len(ids), "task_ids": ids})
    return TaskListResponse(
        items=[TaskResponse(**t) for t in tasks],
        total=len(tasks),
    )


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status_filter: int | None = Query(None, alias="status"),
    channel_id: int | None = None,
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    tasks = task_repo.get_all_tasks(
        status=status_filter,
        channel_id=channel_id,
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
    )
    return TaskListResponse(
        items=[TaskResponse(**t) for t in tasks],
        total=len(tasks),
    )


@router.get("/calendar")
async def task_calendar(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    channel_id: int | None = None,
    user: dict = Depends(get_current_user),
):
    """Tasks grouped by day for calendar view."""
    from collections import defaultdict
    tasks = task_repo.get_all_tasks(
        channel_id=channel_id,
        date_from=date_from,
        date_to=date_to,
        limit=500,
    )
    by_day: dict[str, list] = defaultdict(list)
    for t in tasks:
        day = t["scheduled_at"].strftime("%Y-%m-%d") if t.get("scheduled_at") else "unscheduled"
        by_day[day].append({
            "id": t["id"],
            "title": t.get("title"),
            "channel_id": t["channel_id"],
            "status": t["status"],
            "scheduled_at": t.get("scheduled_at"),
            "media_type": t.get("media_type"),
        })
    return {"days": dict(sorted(by_day.items())), "total": len(tasks)}


@router.get("/history", response_model=TaskListResponse)
async def task_history(
    channel_id: int | None = None,
    status_filter: int | None = Query(None, alias="status"),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Completed/failed/cancelled tasks history."""
    if status_filter is not None:
        statuses_list = None
        single_status = status_filter
    else:
        statuses_list = [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
        single_status = None

    tasks = task_repo.get_all_tasks(
        status=single_status,
        statuses=statuses_list,
        channel_id=channel_id,
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
    )
    return TaskListResponse(
        items=[TaskResponse(**t) for t in tasks],
        total=len(tasks),
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, user: dict = Depends(get_current_user)):
    task = task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, body: TaskUpdate, user: dict = Depends(get_current_user)):
    task = task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if body.scheduled_at is not None:
        if task["status"] not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
            raise HTTPException(status_code=409, detail="Cannot reschedule a task that is already completed or failed")
        task_repo.update_task_scheduled_at(task_id, body.scheduled_at)

    if body.status is not None:
        task_repo.update_task_status(task_id, body.status, error_message=body.error_message)

    updated = task_repo.get_task(task_id)
    return TaskResponse(**updated)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: int, user: dict = Depends(get_current_user)):
    """Cancel a pending or processing task."""
    task = task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
        raise HTTPException(status_code=409, detail="Only pending/processing tasks can be cancelled")

    task_repo.cancel_task(task_id)
    audit_log("task.cancel", actor_id=user.get("id"), entity_type="task", entity_id=task_id)
    updated = task_repo.get_task(task_id)
    return TaskResponse(**updated)


@router.get("/{task_id}/status")
async def get_task_status(task_id: int, user: dict = Depends(get_current_user)):
    task = task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task["id"],
        "status": task["status"],
        "upload_id": task.get("upload_id"),
        "error_message": task.get("error_message"),
        "completed_at": task.get("completed_at"),
    }


@router.get("/{task_id}/progress")
async def get_task_progress(task_id: int, user: dict = Depends(get_current_user)):
    """Get upload progress from Redis (set by publishing worker)."""
    task = task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    progress = _get_progress_from_redis(task_id)
    return {
        "task_id": task["id"],
        "status": task["status"],
        "progress_pct": progress.get("pct", 0),
        "bytes_uploaded": progress.get("bytes_uploaded", 0),
        "total_bytes": progress.get("total_bytes", 0),
        "stage": progress.get("stage", "unknown"),
    }


@router.get("/{task_id}/preview")
async def get_task_preview(task_id: int, user: dict = Depends(get_current_user)):
    """Get file info for task preview (file existence, size, type)."""
    import os
    task = task_repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    source = task.get("source_file_path", "")
    thumb = task.get("thumbnail_path", "")

    source_info = _file_info(source) if source else None
    thumb_info = _file_info(thumb) if thumb else None

    return {
        "task_id": task["id"],
        "source_file": source_info,
        "thumbnail": thumb_info,
        "upload_url": f"https://www.youtube.com/watch?v={task['upload_id']}" if task.get("upload_id") else None,
    }


@router.get("/stats/summary")
async def task_stats(user: dict = Depends(get_current_user)):
    """Aggregate task statistics."""
    from shared.db.connection import get_connection
    from sqlalchemy import text
    sql = text(
        "SELECT status, COUNT(*) as cnt FROM content_upload_queue_tasks GROUP BY status"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()

    status_names = {s.value: s.name.lower() for s in TaskStatus}
    stats = {status_names.get(r[0], f"unknown_{r[0]}"): r[1] for r in rows}
    stats["total"] = sum(r[1] for r in rows)
    return stats


def _file_info(path: str) -> dict | None:
    """Get basic file info without reading content."""
    import os
    if not path or not os.path.exists(path):
        return {"path": path, "exists": False}
    stat = os.stat(path)
    return {
        "path": path,
        "exists": True,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
    }


def _get_progress_from_redis(task_id: int) -> dict:
    """Read progress data from Redis hash."""
    import json as _json
    try:
        from shared.queue.config import get_redis
        r = get_redis()
        raw = r.get(f"task:{task_id}:progress")
        if raw:
            return _json.loads(raw)
    except Exception:
        pass
    return {}
