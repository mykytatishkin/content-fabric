"""DLE ingestion worker — rq worker consuming from 'dle_ingestion' queue."""

from __future__ import annotations

import logging
from typing import Any

from shared.queue.types import DleIngestionPayload
from shared.ingestion.dle.pipeline import DleIngestionPipeline
from shared.notifications import telegram
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


def run_ingestion_job(payload: DleIngestionPayload) -> dict[str, Any]:
    """Job handler called by rq.

    1. Connect to DLE source.
    2. Fetch N recent posts.
    3. For each post: create a CFF task (downloading + processing will follow).
    """
    bootstrap_job(payload, "cff-dle-ingestion")
    logger.info(
        "Running DLE ingestion: source=%s channel=%s limit=%d",
        payload.source_slug, payload.channel_id, payload.limit
    )
    try:
        pipeline = DleIngestionPipeline(payload.source_slug)
        count = pipeline.run(
            channel_id=payload.channel_id,
            limit=payload.limit,
            media_type=payload.media_type
        )
        return {"ok": True, "created_tasks": count}
    except Exception as exc:
        error = str(exc)
        logger.error("DLE ingestion failed for %s: %s", payload.source_slug, error)
        telegram.send(f"DLE ingestion failed for {payload.source_slug}: {error}")
        return {"ok": False, "error": error}


if __name__ == "__main__":
    import shared.env  # noqa: F401 — load .env files

    from rq import Worker

    from shared.queue.config import get_redis, QUEUE_DLE_INGESTION

    from shared.logging_config import setup_logging
    setup_logging(service_name="cff-dle-ingestion")
    redis_conn = get_redis()
    worker = Worker([QUEUE_DLE_INGESTION], connection=redis_conn)
    worker.work()
