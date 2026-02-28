"""Channel statistics repository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_connection


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
        return result.lastrowid


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
