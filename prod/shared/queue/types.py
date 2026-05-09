"""Payload types for queue messages.

Every payload has `trace_id`. Set it at job creation time (or it auto-fills
in publisher.enqueue_*). Workers propagate it via shared.logging_context.
"""

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
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationPayload:
    channel: str  # "telegram" | "email"
    recipient: str
    subject: str | None = None
    message: str = ""
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceChangePayload:
    task_id: int
    source_file_path: str
    output_file_path: str
    voice_model: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Yii migration payloads (feat/yii-integration) ───────────────────


@dataclass
class DleIngestionPayload:
    """Парсинг одного DLE-источника. Результат — N задач в content_upload_queue_tasks."""
    source_slug: str  # "audiokniga_one_com" / "bazaknig_net" / etc.
    channel_id: int   # Целевой YouTube-канал для загрузки
    limit: int = 1    # Сколько постов обработать за один прогон
    media_type: str = "video"  # "video" или "shorts"
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShortsPayload:
    """Нарезка shorts из донорского YouTube-видео."""
    channel_id: int
    donor_video_url: str | None = None  # Если None — взять из конфига канала
    limit: int = 5                       # Кол-во highlights из видео
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SoraPayload:
    """Скрейпинг Sora AI feed → загрузка одного видео."""
    channel_id: int
    feed_url: str = "https://sora.chatgpt.com/backend/public/nf2/feed"
    min_views: int = 1000                # Минимум просмотров для обработки поста
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StatsPayload:
    """Сбор daily statistics для одного или всех YouTube-каналов."""
    channel_id: int | None = None        # None = все enabled каналы
    snapshot_date: str | None = None     # ISO date, None = today
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamControlPayload:
    """Управление RTMP стримом (start / stop / restart / sync)."""
    action: str                          # "start" | "stop" | "restart" | "sync" | "sync_all"
    stream_id: int | None = None         # ID из live_stream_configurations (None для sync_all)
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DleProcessingPayload:
    """Обробка DLE завдання: скачування → voice → відео."""
    task_id: int                         # ID завдання в content_upload_queue_tasks
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
