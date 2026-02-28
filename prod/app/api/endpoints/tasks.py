"""Task management endpoints — creates tasks in DB, scheduler enqueues to Redis."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.audit import log as audit_log
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
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
        statuses_list = [1, 2, 4]  # completed, failed, cancelled
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
        if task["status"] not in (0, 3):
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
    if task["status"] not in (0, 3):
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
