"""Sora pipeline API — feed scraping + meme overlay (Yii classic).

URLs:
    GET  /api/v1/sora/                  → status + processed posts count
    GET  /api/v1/sora/used-posts        → recent processed sora posts
    POST /api/v1/sora/run                → manual enqueue (mode=shorts|meme)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text as sql_text

from app.api.deps import get_current_admin
from shared.db.connection import get_engine
from shared.queue.publisher import enqueue_sora
from shared.queue.types import SoraPayload

logger = logging.getLogger(__name__)
router = APIRouter()


class SoraRunRequest(BaseModel):
    channel_id: int
    limit: int = 3
    mode: str = "shorts"  # "shorts" (Whisper highlights) or "meme" (Yii classic)
    min_views: int = 1000


@router.get("/")
def status(_: dict = Depends(get_current_admin)) -> dict[str, Any]:
    try:
        with get_engine().begin() as conn:
            count_row = conn.execute(
                sql_text("SELECT COUNT(*) AS n FROM sora_used_posts")
            ).first()
            last_row = conn.execute(
                sql_text("SELECT MAX(fetched_at) AS last_at FROM sora_used_posts")
            ).first()
        return {
            "ok": True,
            "used_posts_count": int(count_row[0]) if count_row else 0,
            "last_fetched_at": str(last_row[0]) if last_row and last_row[0] else None,
            "feed_url": "https://sora.chatgpt.com/backend/public/nf2/feed",
            "modes_available": ["shorts", "meme"],
        }
    except Exception as exc:
        logger.exception("sora status failed")
        return {"ok": False, "error": str(exc)}


@router.get("/used-posts")
def used_posts(
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    try:
        with get_engine().begin() as conn:
            rows = conn.execute(sql_text(
                "SELECT post_id, fetched_at, channel_id FROM sora_used_posts "
                "ORDER BY fetched_at DESC LIMIT :l"
            ), {"l": limit}).mappings().all()
        return {"ok": True, "items": [dict(r) for r in rows]}
    except Exception as exc:
        logger.exception("sora used posts failed")
        raise HTTPException(500, f"DB query failed: {exc}")


@router.post("/run")
def run_sora(
    req: SoraRunRequest,
    _: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    if req.mode not in ("shorts", "meme"):
        raise HTTPException(400, "mode must be 'shorts' or 'meme'")

    payload = SoraPayload(
        channel_id=req.channel_id,
        limit=req.limit,
        media_type="shorts",
        min_views=req.min_views,
        metadata={"mode": req.mode},
    )
    try:
        job_id = enqueue_sora(payload)
    except Exception as exc:
        logger.exception("sora enqueue failed")
        raise HTTPException(500, f"enqueue failed: {exc}")

    return {"ok": True, "job_id": job_id, "mode": req.mode,
            "channel_id": req.channel_id, "limit": req.limit}
