"""News pipeline API — RBC RSS → Long video / Shorts.

URLs:
    GET  /api/v1/news/                       → list of channels available + last runs
    GET  /api/v1/news/processed?limit=50      → list of news_processed_urls (history)
    POST /api/v1/news/run                     → manual enqueue (long or shorts)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text as sql_text

from app.api.deps import get_current_admin
from shared.db.connection import get_engine
from shared.queue.publisher import enqueue_news
from shared.queue.types import NewsPayload

logger = logging.getLogger(__name__)
router = APIRouter()


class NewsRunRequest(BaseModel):
    channel_id: int
    media_type: str = "video"   # "video" or "shorts"
    rss_url: str | None = None
    language: str = "uk"
    images_count: int = 5


@router.get("/")
def list_news_status(_: dict = Depends(get_current_admin)) -> dict[str, Any]:
    """Overview: history depth, last processing time."""
    try:
        with get_engine().begin() as conn:
            count_row = conn.execute(
                sql_text("SELECT COUNT(*) AS n FROM news_processed_urls")
            ).first()
            recent_row = conn.execute(
                sql_text("SELECT MAX(processed_at) AS last_at FROM news_processed_urls")
            ).first()
        return {
            "ok": True,
            "processed_urls_count": int(count_row[0]) if count_row else 0,
            "last_processed_at": str(recent_row[0]) if recent_row and recent_row[0] else None,
            "feed_url": "https://www.rbc.ua/static/rss/all.ukr.rss.xml",
        }
    except Exception as exc:
        logger.exception("news status query failed")
        return {"ok": False, "error": str(exc)}


@router.get("/processed")
def list_processed(
    limit: int = Query(50, ge=1, le=500),
    _: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    """Recent N processed URLs (history view)."""
    try:
        with get_engine().begin() as conn:
            rows = conn.execute(sql_text(
                "SELECT link, source, processed_at FROM news_processed_urls "
                "ORDER BY processed_at DESC LIMIT :l"
            ), {"l": limit}).mappings().all()
        return {"ok": True, "items": [dict(r) for r in rows]}
    except Exception as exc:
        logger.exception("news processed list failed")
        raise HTTPException(500, f"DB query failed: {exc}")


@router.post("/run")
def run_news(
    req: NewsRunRequest,
    _: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    """Manually enqueue a news job. Returns job ID."""
    if req.media_type not in ("video", "shorts"):
        raise HTTPException(400, "media_type must be 'video' or 'shorts'")

    payload = NewsPayload(
        channel_id=req.channel_id,
        media_type=req.media_type,
        rss_url=req.rss_url or "https://www.rbc.ua/static/rss/all.ukr.rss.xml",
        language=req.language,
        images_count=req.images_count,
    )
    try:
        job_id = enqueue_news(payload)
    except Exception as exc:
        logger.exception("news enqueue failed")
        raise HTTPException(500, f"enqueue failed: {exc}")

    return {"ok": True, "job_id": job_id, "channel_id": req.channel_id,
            "media_type": req.media_type}
