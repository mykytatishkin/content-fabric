"""Task request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskCreate(BaseModel):
    channel_id: int
    source_file_path: str = Field(..., min_length=1, max_length=1000)
    title: str = Field(..., min_length=1, max_length=500)
    scheduled_at: datetime
    media_type: str = "video"
    thumbnail_path: str | None = Field(None, max_length=1000)
    description: str | None = Field(None, max_length=5000)
    keywords: str | None = Field(None, max_length=2000)
    post_comment: str | None = Field(None, max_length=2000)
    legacy_add_info: dict[str, Any] | None = None

    @field_validator("source_file_path", "thumbnail_path")
    @classmethod
    def validate_file_path(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if ".." in v:
            raise ValueError("Path traversal not allowed")
        if len(v) > 1000:
            raise ValueError("Path too long")
        return v


class TaskUpdate(BaseModel):
    status: int | None = Field(None, ge=0, le=4)
    scheduled_at: datetime | None = None
    error_message: str | None = None


class TaskResponse(BaseModel):
    id: int
    uuid: str | None = None
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


class TaskBatchCreate(BaseModel):
    tasks: list[TaskCreate]


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
