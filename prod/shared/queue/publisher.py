"""Queue publisher — enqueue jobs for workers."""

from __future__ import annotations

from rq import Queue

from shared.queue.config import get_redis, QUEUE_PUBLISHING, QUEUE_NOTIFICATIONS, QUEUE_VOICE
from shared.queue.types import VideoUploadPayload, NotificationPayload, VoiceChangePayload


def _get_queue(name: str) -> Queue:
    return Queue(name, connection=get_redis())


def enqueue_video_upload(payload: VideoUploadPayload, **kwargs) -> str:
    """Enqueue a video upload job. Returns job ID."""
    q = _get_queue(QUEUE_PUBLISHING)
    job = q.enqueue(
        "workers.publishing_worker.process_upload",
        payload,
        job_timeout="30m",
        **kwargs,
    )
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
    return job.id


def enqueue_voice_change(payload: VoiceChangePayload, **kwargs) -> str:
    """Enqueue a voice change job. Returns job ID."""
    q = _get_queue(QUEUE_VOICE)
    job = q.enqueue(
        "workers.voice_worker.process_voice_change",
        payload,
        job_timeout="30m",
        **kwargs,
    )
    return job.id
