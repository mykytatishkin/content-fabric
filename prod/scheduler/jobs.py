"""Scheduler job definitions — poll DB and enqueue to Redis."""

from __future__ import annotations

import logging

from shared.db.models import TaskStatus
from shared.db.repositories import task_repo, channel_repo, console_repo
from shared.queue.publisher import enqueue_video_upload
from shared.queue.types import VideoUploadPayload
from shared.youtube.token_refresh import build_credentials, ensure_fresh_credentials

logger = logging.getLogger(__name__)


def enqueue_pending_tasks() -> int:
    """Find pending tasks (status=0, scheduled_at <= NOW) and push to Redis.

    Returns the number of tasks enqueued.
    """
    tasks = task_repo.get_pending_tasks(limit=50)
    if not tasks:
        logger.info("Poll: 0 pending tasks")
        return 0
    logger.info("Found %d pending tasks to enqueue", len(tasks))

    count = 0
    for t in tasks:
        try:
            # Mark as processing to prevent double-pickup
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
            task_repo.update_task_status(t["id"], TaskStatus.PENDING.value)

    return count


def validate_channel_tokens() -> tuple[int, int]:
    """Try to refresh credentials for all enabled channels with tokens.

    Returns (success_count, failure_count).
    """
    channels = channel_repo.get_channels_with_tokens()
    if not channels:
        logger.info("Token validation: no channels with tokens found")
        return 0, 0

    success = 0
    failure = 0
    for ch in channels:
        try:
            console = console_repo.get_console_by_id(ch["console_id"])
            if not console:
                logger.warning("Channel %s (%s): console_id=%s not found",
                               ch["id"], ch["name"], ch["console_id"])
                channel_repo.update_token_check(ch["id"], ok=False)
                failure += 1
                continue

            creds = build_credentials(
                access_token=ch["access_token"],
                refresh_token=ch["refresh_token"],
                client_id=console["client_id"],
                client_secret=console["client_secret"],
                token_expires_at=ch["token_expires_at"],
            )
            ensure_fresh_credentials(creds, channel_id=ch["id"])
            channel_repo.update_token_check(ch["id"], ok=True)
            success += 1
            logger.info("Token OK: channel %s (%s)", ch["id"], ch["name"])
        except Exception:
            logger.exception("Token FAILED: channel %s (%s)", ch["id"], ch["name"])
            channel_repo.update_token_check(ch["id"], ok=False)
            failure += 1

    logger.info("Token validation: %d ok, %d failed", success, failure)
    return success, failure
