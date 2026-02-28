"""YouTube upload orchestration — ties together client + DB + notifications."""

from __future__ import annotations

import logging
from typing import Any

from shared.db.repositories import channel_repo, console_repo, task_repo
from shared.notifications import telegram
from shared.queue.types import VideoUploadPayload
from shared.youtube import client as yt

logger = logging.getLogger(__name__)

MAX_UPLOAD_ATTEMPTS = 2  # allows one retry after token refresh


def process_upload(payload: VideoUploadPayload) -> dict[str, Any]:
    """Full upload pipeline for a single task.

    1. Load channel + console creds from DB
    2. Create YouTube service (auto-refresh tokens)
    3. Upload video
    4. Set thumbnail, auto-like, post comment
    5. Mark task completed / failed
    """
    task_id = payload.task_id
    channel_id = payload.channel_id

    task_repo.mark_task_processing(task_id)

    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel:
        _fail(task_id, f"Channel {channel_id} not found")
        return {"ok": False, "error": "channel_not_found"}

    console = console_repo.get_console_by_id(channel["console_id"]) if channel.get("console_id") else None
    if not console:
        _fail(task_id, f"OAuth console not found for channel {channel_id}")
        return {"ok": False, "error": "console_not_found"}

    # Build tags list from comma-separated keywords
    tags: list[str] = []
    if payload.keywords:
        tags = [t.strip() for t in payload.keywords.split(",") if t.strip()]

    last_error = ""
    for attempt in range(MAX_UPLOAD_ATTEMPTS):
        try:
            service, creds = yt.create_service(
                access_token=channel["access_token"],
                refresh_token=channel["refresh_token"],
                client_id=console["client_id"],
                client_secret=console["client_secret"],
                token_expires_at=channel.get("token_expires_at"),
                channel_id=channel_id,
            )

            response = yt.upload_video(
                service=service,
                file_path=payload.source_file_path,
                title=payload.title,
                description=payload.description,
                tags=tags,
                thumbnail_path=payload.thumbnail_path,
            )

            video_id = response.get("id", "")
            task_repo.mark_task_completed(task_id, upload_id=video_id)

            # post-upload actions
            yt.like_video(service, video_id)
            if payload.post_comment and video_id:
                yt.post_comment(service, video_id, payload.post_comment)

            logger.info("Task %d completed: video_id=%s", task_id, video_id)
            return {"ok": True, "video_id": video_id}

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Upload attempt %d/%d failed for task %d: %s",
                attempt + 1, MAX_UPLOAD_ATTEMPTS, task_id, last_error,
            )
            # If token error, reload channel from DB for retry
            if attempt < MAX_UPLOAD_ATTEMPTS - 1:
                channel = channel_repo.get_channel_by_id(channel_id) or channel

    _fail(task_id, last_error)
    return {"ok": False, "error": last_error}


def _fail(task_id: int, error: str) -> None:
    logger.error("Task %d failed: %s", task_id, error)
    task_repo.mark_task_failed(task_id, error)
    telegram.send(f"Upload task {task_id} failed: {error}")
