"""Publishing worker — rq worker consuming from 'publishing' queue."""

from __future__ import annotations

import logging
from typing import Any

from shared.queue.types import VideoUploadPayload
from shared.youtube.upload import process_upload

logger = logging.getLogger(__name__)


def process_upload_job(payload: VideoUploadPayload) -> dict[str, Any]:
    """Job handler called by rq."""
    logger.info("Processing upload: task_id=%d channel_id=%d", payload.task_id, payload.channel_id)
    return process_upload(payload)


if __name__ == "__main__":
    import shared.env  # noqa: F401 — load .env files

    from rq import Worker

    from shared.queue.config import get_redis, QUEUE_PUBLISHING

    from shared.logging_config import setup_logging
    setup_logging(service_name="cff-publishing")
    redis_conn = get_redis()
    worker = Worker([QUEUE_PUBLISHING], connection=redis_conn)
    worker.work()
