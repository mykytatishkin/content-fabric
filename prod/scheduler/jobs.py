"""Scheduler job definitions — poll DB and enqueue to Redis."""

from __future__ import annotations

import logging

from shared.db.models import TaskStatus
from shared.db.repositories import task_repo, channel_repo
from shared.queue.publisher import enqueue_video_upload
from shared.queue.types import VideoUploadPayload

logger = logging.getLogger(__name__)


def enqueue_pending_tasks() -> int:
    """Find pending tasks (status=0, scheduled_at <= NOW) and push to Redis.

    Returns the number of tasks enqueued.
    """
    tasks = task_repo.get_pending_tasks(limit=50)
    if not tasks:
        return 0

    count = 0
    for t in tasks:
        try:
            # Mark as processing to prevent double-pickup by legacy worker
            task_repo.mark_task_processing(t["id"])

            enqueue_video_upload(VideoUploadPayload(
                task_id=t["id"],
                channel_id=t["channel_id"],
                source_file_path=t["source_file_path"] or "",
                title=t["title"] or "",
                description=t.get("description"),
                keywords=t.get("keywords"),
                thumbnail_path=t.get("thumbnail_path"),
                post_comment=t.get("post_comment"),
                media_type=t.get("media_type", "video"),
            ))
            count += 1
            logger.info("Enqueued task %d for channel %d", t["id"], t["channel_id"])
        except Exception:
            logger.exception("Failed to enqueue task %d", t["id"])
            # Reset back to pending so it can be retried
            task_repo.update_task_status(t["id"], TaskStatus.PENDING)

    return count
