"""DLE sources API — управление 7 внешними источниками контента.

URLs:
    GET  /api/v1/dle-sources/                  → список + статус подключения каждого
    POST /api/v1/dle-sources/{slug}/run-now    → enqueue ingestion job
    GET  /api/v1/dle-sources/{slug}/preview?limit=5 → последние N постов из источника
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_admin
from app.core.config import dle_settings
from shared.queue.publisher import enqueue_dle_ingestion
from shared.queue.types import DleIngestionPayload

logger = logging.getLogger(__name__)
router = APIRouter()


class RunNowRequest(BaseModel):
    channel_id: int
    limit: int = 1
    media_type: str = "video"


def _mask_dsn(dsn: str) -> str:
    """Скрыть пароль в DSN для отображения."""
    if "@" not in dsn:
        return dsn
    creds, host = dsn.split("@", 1)
    if "://" in creds:
        proto, userinfo = creds.split("://", 1)
        if ":" in userinfo:
            user = userinfo.split(":", 1)[0]
            return f"{proto}://{user}:***@{host}"
    return f"***@{host}"


def _check_connection(slug: str, dsn: str) -> dict[str, Any]:
    """Быстрая проверка подключения (SELECT 1 с timeout)."""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(dsn, pool_pre_ping=False, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


@router.get("/")
async def list_sources(user: dict = Depends(get_current_admin)):
    sources = []
    for slug, dsn in dle_settings.all_sources().items():
        sources.append({
            "slug": slug,
            "dsn_masked": _mask_dsn(dsn),
        })
    return {"sources": sources}


@router.get("/status")
async def status_sources(user: dict = Depends(get_current_admin)):
    """Полный статус с проверкой подключения каждого источника."""
    sources = []
    for slug, dsn in dle_settings.all_sources().items():
        check = _check_connection(slug, dsn)
        sources.append({
            "slug": slug,
            "dsn_masked": _mask_dsn(dsn),
            "connected": check["ok"],
            "error": check.get("error"),
        })
    return {"sources": sources}


@router.post("/{slug}/run-now")
async def run_now(slug: str, body: RunNowRequest, user: dict = Depends(get_current_admin)):
    """Enqueue DLE ingestion для одного источника прямо сейчас."""
    if slug not in dle_settings.all_sources():
        raise HTTPException(status_code=404, detail=f"DLE source '{slug}' not configured")

    job_id = enqueue_dle_ingestion(DleIngestionPayload(
        source_slug=slug,
        channel_id=body.channel_id,
        limit=body.limit,
        media_type=body.media_type,
    ))
    return {"ok": True, "job_id": job_id, "source": slug, "channel_id": body.channel_id}


@router.get("/{slug}/preview")
async def preview(
    slug: str,
    limit: int = Query(5, ge=1, le=50),
    user: dict = Depends(get_current_admin),
):
    """Прочитать последние N постов из источника без создания задач."""
    dsn = dle_settings.all_sources().get(slug)
    if not dsn:
        raise HTTPException(status_code=404, detail=f"DLE source '{slug}' not configured")

    from shared.ingestion.dle.client import DleClient
    try:
        client = DleClient(dsn, slug)
        posts = client.fetch_recent_posts(limit=limit)
    except Exception as exc:
        logger.exception("DLE preview failed for %s", slug)
        raise HTTPException(status_code=502, detail=str(exc))

    # Возвращаем только нужное (без xfields и full_story для скорости)
    result = []
    for p in posts:
        result.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "alt_name": p.get("alt_name"),
            "category": p.get("category"),
            "date": str(p.get("date")) if p.get("date") else None,
            "normalized": p.get("normalized") or {},
        })
    return {"source": slug, "posts": result, "count": len(result)}
