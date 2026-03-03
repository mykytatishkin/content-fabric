"""Queue publisher — enqueue jobs for workers."""

from __future__ import annotations

import logging

from rq import Queue

from shared.queue.config import get_redis, QUEUE_PUBLISHING, QUEUE_NOTIFICATIONS, QUEUE_VOICE
from shared.queue.types import VideoUploadPayload, NotificationPayload, VoiceChangePayload

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
