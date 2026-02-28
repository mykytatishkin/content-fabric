"""Schedule template schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class SlotCreate(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    time_utc: str  # HH:MM format
    channel_id: int | None = None
    media_type: str = "video"

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("day_of_week must be 0-6 (Monday-Sunday)")
        return v

    @field_validator("time_utc")
    @classmethod
    def validate_time(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("time_utc must be HH:MM")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid time")
        return f"{h:02d}:{m:02d}"


class SlotResponse(BaseModel):
    id: int
    template_id: int
    day_of_week: int
    time_utc: str
    channel_id: int | None = None
    media_type: str = "video"
    enabled: bool = True


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    timezone: str = "UTC"
    slots: list[SlotCreate] = []


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str | None = None
    timezone: str = "UTC"
    is_active: bool = True
    slots: list[SlotResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int
