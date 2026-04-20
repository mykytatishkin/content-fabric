"""Notification repository."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_connection

logger = logging.getLogger(__name__)


def get_notifications(user_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    sql = text(
        "SELECT id, user_id, type, title, message, is_read, created_at "
        "FROM notifications WHERE user_id = :uid ORDER BY created_at DESC LIMIT :lim OFFSET :off"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, {"uid": user_id, "lim": limit, "off": offset}).fetchall()
    return [
        {"id": r[0], "user_id": r[1], "type": r[2], "title": r[3],
         "message": r[4], "is_read": bool(r[5]), "created_at": r[6]}
        for r in rows
    ]


def count_unread(user_id: int) -> int:
    sql = text("SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = 0")
    with get_connection() as conn:
        return conn.execute(sql, {"uid": user_id}).scalar() or 0


def mark_read(notification_id: int, user_id: int) -> None:
    sql = text("UPDATE notifications SET is_read = 1 WHERE id = :nid AND user_id = :uid")
    with get_connection() as conn:
        conn.execute(sql, {"nid": notification_id, "uid": user_id})


def mark_all_read(user_id: int) -> None:
    sql = text("UPDATE notifications SET is_read = 1 WHERE user_id = :uid AND is_read = 0")
    with get_connection() as conn:
        conn.execute(sql, {"uid": user_id})


def create(user_id: int, type: str, title: str, message: str | None = None) -> int:
    sql = text(
        "INSERT INTO notifications (user_id, type, title, message, is_read, created_at) "
        "VALUES (:uid, :type, :title, :msg, 0, NOW())"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"uid": user_id, "type": type, "title": title, "msg": message})
        return result.lastrowid


def broadcast(title: str, message: str | None = None) -> int:
    """Send notification to all active users. Returns count."""
    sql = text(
        "INSERT INTO notifications (user_id, type, title, message, is_read, created_at) "
        "SELECT id, 'broadcast', :title, :msg, 0, NOW() FROM platform_users WHERE status IN (1, 10)"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {"title": title, "msg": message})
        count = result.rowcount
    logger.info("Broadcast sent to %d users: %s", count, title)
    return count


def delete(notification_id: int, user_id: int) -> None:
    sql = text("DELETE FROM notifications WHERE id = :nid AND user_id = :uid")
    with get_connection() as conn:
        conn.execute(sql, {"nid": notification_id, "uid": user_id})
