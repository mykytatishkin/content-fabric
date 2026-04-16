"""Channel statistics repository."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_connection

logger = logging.getLogger(__name__)


def get_channel_stats(channel_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Get daily statistics for a channel over the last N days."""
    sql = text(
        "SELECT snapshot_date, subscribers, views, videos, likes, comments "
        "FROM channel_daily_statistics "
        "WHERE channel_id = :cid AND snapshot_date >= DATE_SUB(NOW(), INTERVAL :days DAY) "
        "ORDER BY snapshot_date DESC"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, {"cid": channel_id, "days": days}).mappings().fetchall()
    return [dict(r) for r in rows]


def record_stats(
    channel_id: int,
    platform_channel_id: str,
    subscribers: int | None = None,
    views: int | None = None,
    videos: int | None = None,
    likes: int | None = None,
    comments: int | None = None,
) -> int:
    """Insert a daily snapshot. Returns new row ID."""
    sql = text(
        "INSERT INTO channel_daily_statistics "
        "(channel_id, platform_channel_id, snapshot_date, subscribers, views, videos, likes, comments, created_at) "
        "VALUES (:cid, :pcid, NOW(), :subs, :views, :vids, :likes, :comments, NOW())"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "cid": channel_id, "pcid": platform_channel_id,
            "subs": subscribers, "views": views, "vids": videos,
            "likes": likes, "comments": comments,
        })
        logger.info("Stats recorded: channel=%s subs=%s views=%s videos=%s", channel_id, subscribers, views, videos)
        return result.lastrowid


def get_video_stats(task_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Get daily statistics for a video (task) over the last N days."""
    sql = text(
        "SELECT snapshot_date, views, likes, dislikes, comments, favorites "
        "FROM video_statistics "
        "WHERE task_id = :tid AND snapshot_date >= DATE_SUB(NOW(), INTERVAL :days DAY) "
        "ORDER BY snapshot_date ASC"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, {"tid": task_id, "days": days}).mappings().fetchall()
    return [dict(r) for r in rows]


def record_video_stats(
    task_id: int,
    channel_id: int,
    upload_id: str,
    views: int = 0,
    likes: int = 0,
    dislikes: int = 0,
    comments: int = 0,
    favorites: int = 0,
) -> int:
    """Insert a daily video snapshot. Returns new row ID."""
    sql = text(
        "INSERT INTO video_statistics "
        "(task_id, channel_id, upload_id, snapshot_date, views, likes, dislikes, comments, favorites, created_at) "
        "VALUES (:tid, :cid, :uid, CURDATE(), :views, :likes, :dislikes, :comments, :favorites, NOW()) "
        "ON DUPLICATE KEY UPDATE views=:views, likes=:likes, dislikes=:dislikes, comments=:comments, favorites=:favorites"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "tid": task_id, "cid": channel_id, "uid": upload_id,
            "views": views, "likes": likes, "dislikes": dislikes,
            "comments": comments, "favorites": favorites,
        })
        return result.lastrowid


def get_completed_tasks_with_upload_id() -> list[dict[str, Any]]:
    """Get all completed tasks that have a YouTube upload_id."""
    sql = text(
        "SELECT id, channel_id, upload_id "
        "FROM content_upload_queue_tasks "
        "WHERE status = 1 AND upload_id IS NOT NULL AND upload_id != ''"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]


def get_all_channels_latest_stats() -> list[dict[str, Any]]:
    """Get the most recent stats snapshot for each channel."""
    sql = text(
        "SELECT s.* FROM channel_daily_statistics s "
        "INNER JOIN ("
        "  SELECT channel_id, MAX(snapshot_date) as max_date "
        "  FROM channel_daily_statistics GROUP BY channel_id"
        ") latest ON s.channel_id = latest.channel_id AND s.snapshot_date = latest.max_date"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return [dict(r) for r in rows]
