"""YouTube upload orchestration — ties together client + DB + notifications."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from shared.db.repositories import channel_repo, console_repo, task_repo
from shared.notifications import telegram
from shared.queue.types import VideoUploadPayload
from shared.youtube import client as yt

_audit_logger = logging.getLogger("audit.worker")

logger = logging.getLogger(__name__)

MAX_UPLOAD_ATTEMPTS = 2  # allows one retry after token refresh


def _set_progress(task_id: int, stage: str, pct: int = 0, **extra: Any) -> None:
    """Write upload progress to Redis for polling by API."""
    try:
        from shared.queue.config import get_redis
        r = get_redis()
        data = {"stage": stage, "pct": pct, **extra}
        r.set(f"task:{task_id}:progress", json.dumps(data), ex=3600)
    except Exception:
        pass  # non-critical


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
    _set_progress(task_id, "preparing", 0)

    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel:
        _fail(task_id, f"Channel {channel_id} not found")
        return {"ok": False, "error": "channel_not_found"}

    console = console_repo.get_console_by_id(channel["console_id"]) if channel.get("console_id") else None
    if not console:
        _fail(task_id, f"OAuth console not found for channel {channel_id}")
        return {"ok": False, "error": "console_not_found"}

    # File size for progress tracking
    total_bytes = 0
    try:
        total_bytes = os.path.getsize(payload.source_file_path)
    except OSError:
        pass

    # Build tags list from comma-separated keywords
    tags: list[str] = []
    if payload.keywords:
        tags = [t.strip() for t in payload.keywords.split(",") if t.strip()]

    last_error = ""
    for attempt in range(MAX_UPLOAD_ATTEMPTS):
        try:
            _set_progress(task_id, "authenticating", 10)

            service, creds = yt.create_service(
                access_token=channel["access_token"],
                refresh_token=channel["refresh_token"],
                client_id=console["client_id"],
                client_secret=console["client_secret"],
                token_expires_at=channel.get("token_expires_at"),
                channel_id=channel_id,
            )

            _set_progress(task_id, "uploading", 20, total_bytes=total_bytes)

            response = yt.upload_video(
                service=service,
                file_path=payload.source_file_path,
                title=payload.title,
                description=payload.description,
                tags=tags,
                thumbnail_path=payload.thumbnail_path,
            )

            video_id = response.get("id", "")
            _set_progress(task_id, "post_processing", 80, bytes_uploaded=total_bytes, total_bytes=total_bytes)

            task_repo.mark_task_completed(task_id, upload_id=video_id)

            # post-upload actions
            yt.like_video(service, video_id)
            if payload.post_comment and video_id:
                yt.post_comment(service, video_id, payload.post_comment)

            _set_progress(task_id, "completed", 100, bytes_uploaded=total_bytes, total_bytes=total_bytes)

            logger.info("Task %d completed: video_id=%s", task_id, video_id)
            _audit_logger.info("task.completed task_id=%d channel_id=%d video_id=%s", task_id, channel_id, video_id)
            return {"ok": True, "video_id": video_id}

        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Upload attempt %d/%d failed for task %d: %s",
                attempt + 1, MAX_UPLOAD_ATTEMPTS, task_id, last_error,
            )
            _set_progress(task_id, "retrying", 0)
            # If token error, reload channel from DB for retry
            if attempt < MAX_UPLOAD_ATTEMPTS - 1:
                channel = channel_repo.get_channel_by_id(channel_id) or channel

    _fail(task_id, last_error, channel_id=channel_id)
    return {"ok": False, "error": last_error}


_TOKEN_ERROR_PATTERNS = ["invalid_grant", "Token has been expired or revoked", "token expired"]


def _is_token_error(error: str) -> bool:
    return any(p.lower() in error.lower() for p in _TOKEN_ERROR_PATTERNS)


def _fail(task_id: int, error: str, channel_id: int | None = None) -> None:
    logger.error("Task %d failed: %s", task_id, error)
    _audit_logger.info("task.failed task_id=%d error=%s", task_id, error[:200])
    _set_progress(task_id, "failed", 0)
    task_repo.mark_task_failed(task_id, error)

    if _is_token_error(error) and channel_id:
        channel = channel_repo.get_channel_by_id(channel_id)
        ch_name = channel["name"] if channel else f"id={channel_id}"
        telegram.send(
            f"Token expired for channel '{ch_name}' (id={channel_id}). "
            f"Re-authorization required. Run: "
            f"python3 run_youtube_reauth.py {ch_name}"
        )
    else:
        telegram.send(f"Upload task {task_id} failed: {error}")
