"""Repository for Sora-feed bookkeeping (used posts).

Replaces the legacy Yii used_posts.txt file (SoraController.actionGet_video).
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from shared.db.connection import get_connection

logger = logging.getLogger(__name__)


def get_used_post_ids() -> set[str]:
    """Return the set of all post_id values previously seen."""
    sql = text("SELECT post_id FROM sora_used_posts")
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return {r[0] for r in rows}


def mark_post_used(post_id: str, channel_id: int | None = None) -> None:
    """Record a Sora post as consumed. Idempotent (INSERT IGNORE)."""
    sql = text(
        "INSERT IGNORE INTO sora_used_posts (post_id, fetched_at, channel_id) "
        "VALUES (:pid, NOW(), :cid)"
    )
    with get_connection() as conn:
        conn.execute(sql, {"pid": post_id, "cid": channel_id})


def is_post_used(post_id: str) -> bool:
    """Check whether a single post_id was already consumed."""
    sql = text("SELECT 1 FROM sora_used_posts WHERE post_id = :pid LIMIT 1")
    with get_connection() as conn:
        row = conn.execute(sql, {"pid": post_id}).fetchone()
    return row is not None
