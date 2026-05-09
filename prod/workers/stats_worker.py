"""Daily stats collection worker."""

from __future__ import annotations

import logging
from typing import Any

from shared.queue.types import StatsPayload
from scheduler.jobs import collect_channel_stats, collect_video_stats
from shared.notifications import telegram
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


def run_stats_job(payload: StatsPayload) -> dict[str, Any]:
    """Job handler called by rq.

    Collect YouTube stats for channels and videos.
    """
    bootstrap_job(payload, "cff-stats")
    logger.info("Running daily stats collection")
    try:
        ch_ok, ch_fail = collect_channel_stats()
        vid_ok, vid_fail = collect_video_stats()
        
        summary = f"Stats collection complete: Channels({ch_ok} ok, {ch_fail} fail), Videos({vid_ok} ok, {vid_fail} fail)"
        logger.info(summary)
        # telegram.send(summary)
        
        return {
            "ok": True, 
            "channels": {"ok": ch_ok, "fail": ch_fail},
            "videos": {"ok": vid_ok, "fail": vid_fail}
        }
    except Exception as exc:
        error = str(exc)
        logger.error("Stats collection failed: %s", error)
        telegram.send(f"Stats collection failed: {error}")
        return {"ok": False, "error": error}


if __name__ == "__main__":
    import shared.env  # noqa: F401 — load .env files

    from rq import Worker

    from shared.queue.config import get_redis, QUEUE_STATS

    from shared.logging_config import setup_logging
    setup_logging(service_name="cff-stats")
    redis_conn = get_redis()
    worker = Worker([QUEUE_STATS], connection=redis_conn)
    worker.work()
