"""Voice change worker — rq worker consuming from 'voice' queue."""

from __future__ import annotations

import logging
from typing import Any

from shared.queue.types import VoiceChangePayload
from shared.voice.changer import process_voice_change
from shared.notifications import telegram

logger = logging.getLogger(__name__)


def process_voice_change_job(payload: VoiceChangePayload) -> dict[str, Any]:
    """Job handler called by rq."""
    logger.info(
        "Processing voice change: task_id=%d source=%s",
        payload.task_id, payload.source_file_path,
    )
    try:
        result = process_voice_change(
            source_file_path=payload.source_file_path,
            output_file_path=payload.output_file_path,
            voice_model=payload.voice_model,
        )
        return {"ok": True, **result}
    except Exception as exc:
        error = str(exc)
        logger.error("Voice change failed for task %d: %s", payload.task_id, error)
        telegram.send(f"Voice change task {payload.task_id} failed: {error}")
        return {"ok": False, "error": error}


if __name__ == "__main__":
    import shared.env  # noqa: F401 — load .env files

    from rq import Worker

    from shared.queue.config import get_redis, QUEUE_VOICE

    from shared.logging_config import setup_logging
    setup_logging(service_name="cff-voice")
    redis_conn = get_redis()
    worker = Worker([QUEUE_VOICE], connection=redis_conn)
    worker.work()
