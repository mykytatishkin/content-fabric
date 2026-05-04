"""Queue publisher — enqueue jobs for workers."""

from __future__ import annotations

import logging

from rq import Queue

from shared.queue.config import (
    get_redis,
    QUEUE_PUBLISHING,
    QUEUE_NOTIFICATIONS,
    QUEUE_VOICE,
    QUEUE_DLE_INGESTION,
    QUEUE_SHORTS,
    QUEUE_SORA,
    QUEUE_STATS,
    QUEUE_STREAM_CONTROL,
)
from shared.queue.types import (
    VideoUploadPayload,
    NotificationPayload,
    VoiceChangePayload,
    DleIngestionPayload,
    ShortsPayload,
    SoraPayload,
    StatsPayload,
    StreamControlPayload,
)

logger = logging.getLogger(__name__)


def _get_queue(name: str) -> Queue:
    return Queue(name, connection=get_redis())


def enqueue_video_upload(payload: VideoUploadPayload, **kwargs) -> str:
    """Enqueue a video upload job. Returns job ID."""
    q = _get_queue(QUEUE_PUBLISHING)
    job = q.enqueue(
        "workers.publishing_worker.process_upload_job",
        payload,
        job_timeout="30m",
        **kwargs,
    )
    logger.info("Enqueued video upload: job=%s task=%s", job.id, getattr(payload, "task_id", "?"))
    return job.id


def enqueue_notification(payload: NotificationPayload, **kwargs) -> str:
    """Enqueue a notification job. Returns job ID."""
    q = _get_queue(QUEUE_NOTIFICATIONS)
    job = q.enqueue(
        "workers.notification_worker.send_notification",
        payload,
        job_timeout="2m",
        **kwargs,
    )
    logger.info("Enqueued notification: job=%s", job.id)
    return job.id


def enqueue_voice_change(payload: VoiceChangePayload, **kwargs) -> str:
    """Enqueue a voice change job. Returns job ID."""
    q = _get_queue(QUEUE_VOICE)
    job = q.enqueue(
        "workers.voice_worker.process_voice_change_job",
        payload,
        job_timeout="30m",
        **kwargs,
    )
    logger.info("Enqueued voice change: job=%s", job.id)
    return job.id


# ─── Yii migration enqueuers (feat/yii-integration) ──────────────────


def enqueue_dle_ingestion(payload: DleIngestionPayload, **kwargs) -> str:
    """Enqueue парсинг одного DLE-источника. Worker создаст N задач в БД."""
    q = _get_queue(QUEUE_DLE_INGESTION)
    job = q.enqueue(
        "workers.dle_ingestion_worker.run_ingestion_job",
        payload,
        job_timeout="20m",  # Скачивание MP3 + voice change может быть долгим
        **kwargs,
    )
    logger.info("Enqueued DLE ingestion: job=%s source=%s channel=%s", job.id, payload.source_slug, payload.channel_id)
    return job.id


def enqueue_shorts(payload: ShortsPayload, **kwargs) -> str:
    """Enqueue нарезка shorts из донорского видео (yt-dlp + Whisper + GPT + ffmpeg)."""
    q = _get_queue(QUEUE_SHORTS)
    job = q.enqueue(
        "workers.shorts_worker.run_shorts_job",
        payload,
        job_timeout="40m",  # Whisper транскрипция и GPT highlights могут долго
        **kwargs,
    )
    logger.info("Enqueued shorts: job=%s channel=%s", job.id, payload.channel_id)
    return job.id


def enqueue_sora(payload: SoraPayload, **kwargs) -> str:
    """Enqueue скрейпинг Sora AI → загрузка видео."""
    q = _get_queue(QUEUE_SORA)
    job = q.enqueue(
        "workers.sora_worker.run_sora_job",
        payload,
        job_timeout="20m",
        **kwargs,
    )
    logger.info("Enqueued sora: job=%s channel=%s", job.id, payload.channel_id)
    return job.id


def enqueue_stats(payload: StatsPayload, **kwargs) -> str:
    """Enqueue сбор daily statistics для канала(ов)."""
    q = _get_queue(QUEUE_STATS)
    job = q.enqueue(
        "workers.stats_worker.run_stats_job",
        payload,
        job_timeout="10m",
        **kwargs,
    )
    logger.info("Enqueued stats: job=%s channel=%s", job.id, payload.channel_id or "ALL")
    return job.id


def enqueue_stream_control(payload: StreamControlPayload, **kwargs) -> str:
    """Enqueue управление RTMP стримом (start/stop/restart/sync)."""
    q = _get_queue(QUEUE_STREAM_CONTROL)
    job = q.enqueue(
        "workers.stream_worker.run_stream_control_job",
        payload,
        job_timeout="5m",
        **kwargs,
    )
    logger.info("Enqueued stream control: job=%s action=%s stream=%s", job.id, payload.action, payload.stream_id)
    return job.id
