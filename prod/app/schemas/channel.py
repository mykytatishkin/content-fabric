"""Channel schemas."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Latin letters, digits, spaces, underscore, hyphen
LATIN_PATTERN = re.compile(r"^[a-zA-Z0-9\s_\-]+$")


class GoogleConsole(BaseModel):
    """Google Console for dropdown."""

    id: int
    name: str
    description: str | None = None
    enabled: bool = True


class ChannelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    channel_id: str = Field(..., min_length=1, max_length=255)
    console_id: int | None = None
    console_name: str | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_latin_only(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Название не может быть пустым")
        v = v.strip()
        if not LATIN_PATTERN.match(v):
            raise ValueError("Название только латиницей (a-z, 0-9, пробел, _ -)")
        return v

    @field_validator("channel_id")
    @classmethod
    def channel_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Channel ID не может быть пустым")
        return v.strip()


class ChannelCreate(ChannelBase):
    """Schema for creating a channel."""

    user_id: UUID | None = None


class Channel(ChannelBase):
    """Channel response schema."""

    id: int
    user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
