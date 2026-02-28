"""Task request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TaskCreate(BaseModel):
    channel_id: int
    source_file_path: str
    title: str
    scheduled_at: datetime
    media_type: str = "video"
    thumbnail_path: str | None = None
    description: str | None = None
    keywords: str | None = None
    post_comment: str | None = None
    legacy_add_info: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    status: int | None = None
    error_message: str | None = None


class TaskResponse(BaseModel):
    id: int
    channel_id: int
    media_type: str | None = None
    status: int
    source_file_path: str | None = None
    thumbnail_path: str | None = None
    title: str | None = None
    description: str | None = None
    keywords: str | None = None
    post_comment: str | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None
    upload_id: str | None = None
    error_message: str | None = None
    retry_count: int | None = None
    created_at: datetime | None = None


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
