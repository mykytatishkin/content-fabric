"""Task management endpoints — creates tasks in DB, scheduler enqueues to Redis."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
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
    return TaskResponse(**task)


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status_filter: int | None = Query(None, alias="status"),
    channel_id: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    tasks = task_repo.get_all_tasks(status=status_filter, channel_id=channel_id, limit=limit)
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

    if body.status is not None:
        task_repo.update_task_status(task_id, body.status, error_message=body.error_message)

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
