"""Payload types for queue messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class VideoUploadPayload:
    task_id: int
    channel_id: int
    source_file_path: str
    title: str
    description: str | None = None
    keywords: str | None = None
    thumbnail_path: str | None = None
    post_comment: str | None = None
    media_type: str = "video"
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationPayload:
    channel: str  # "telegram" | "email"
    recipient: str
    subject: str | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceChangePayload:
    task_id: int
    source_file_path: str
    output_file_path: str
    voice_model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
