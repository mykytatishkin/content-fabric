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
    limit: int = 3                       # Сколько новых постов скачать за раз
    media_type: str = "shorts"           # "shorts" или "video"
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


@dataclass
class DleQuotesShortsPayload:
    """1 цитата з quotes.txt → 1080×1920 short з ASS-субтитрами + bg_music.

    1:1 порт всіх 7 Yii ``actionShorts`` (Audiokniga, Bazaknig, Books_online_info,
    Club_books_ru, Knigi_online_club, Slushat_knigi_com, Unique_audio).
    """
    source_slug: str             # "audiokniga_one_com" / "bazaknig_net" / etc.
    channel_id: int              # Цільовий YouTube-канал
    quotes_file: str             # Шлях до quotes.txt (per-source)
    backgrounds_dir: str         # Папка з фоновими картинками
    bg_music_dir: str            # Папка з bg_music/*.mp3
    language: str = "ru"         # TTS мова
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NewsPayload:
    """RBC RSS → 5 фото SerpAPI → TTS → Ken Burns slideshow або vertical shorts.

    1:1 порт Yii ``NewsController::actionUpload_to_youtube`` /
    ``NewsController::actionShorts``.
    """
    channel_id: int                              # Цільовий YouTube-канал
    media_type: str = "video"                    # "video" (long) або "shorts"
    rss_url: str = "https://www.rbc.ua/static/rss/all.ukr.rss.xml"
    language: str = "uk"                         # TTS мова
    images_count: int = 5                        # Скільки фото для slideshow
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
