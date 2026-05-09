"""Publishing worker — rq worker consuming from 'publishing' queue."""

from __future__ import annotations

import logging
from typing import Any

from shared.metrics import instrument_job
from shared.queue.types import VideoUploadPayload
from shared.youtube.upload import process_upload
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


@instrument_job("publishing")
def process_upload_job(payload: VideoUploadPayload) -> dict[str, Any]:
    """Job handler called by rq."""
    bootstrap_job(payload, "cff-publishing")
    logger.info("Processing upload: task_id=%d channel_id=%d", payload.task_id, payload.channel_id)
    return process_upload(payload)


if __name__ == "__main__":
    from shared.queue.config import QUEUE_PUBLISHING
    from shared.queue.worker_runner import main
    main([QUEUE_PUBLISHING], "cff-publishing")
