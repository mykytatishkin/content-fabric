"""Voice change worker — rq worker consuming from 'voice' queue."""

from __future__ import annotations

import logging
import time
from typing import Any

from shared.metrics import instrument_job
from shared.queue.types import VoiceChangePayload
from shared.voice.changer import process_voice_change
from shared.notifications import telegram
from shared.db.repositories import task_repo
from shared.db.models import TaskStatus
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


@instrument_job("voice")
def process_voice_change_job(payload: VoiceChangePayload) -> dict[str, Any]:
    """Job handler called by rq.

    Includes retry logic for missing source files: 3 attempts before failure.
    """
    bootstrap_job(payload, "cff-voice")
    task_id = payload.task_id
    source_path = payload.source_file_path

    logger.info("Processing voice change: task_id=%d source=%s", task_id, source_path)
    
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            if not source_path:
                 raise FileNotFoundError(f"Source file path is empty for task {task_id}")

            result = process_voice_change(
                source_file_path=source_path,
                output_file_path=payload.output_file_path,
                voice_model=payload.voice_model,
            )
            return {"ok": True, **result}
            
        except FileNotFoundError as exc:
            error = str(exc)
            if attempt < max_retries:
                logger.warning("Attempt %d/%d failed for task %d: %s. Retrying in %ds...", 
                               attempt, max_retries, task_id, error, retry_delay)
                time.sleep(retry_delay)
                continue
            
            logger.error("All %d attempts failed for task %d: %s", max_retries, task_id, error)
            task_repo.update_task_status(task_id, TaskStatus.FAILED.value, error_message=f"Missing source file after {max_retries} attempts")
            telegram.send(f"Voice change task {task_id} failed: {error}")
            return {"ok": False, "error": error}
            
        except Exception as exc:
            error = str(exc)
            logger.error("Voice change CRITICAL failure for task %d: %s", task_id, error)
            task_repo.update_task_status(task_id, TaskStatus.FAILED.value, error_message=error)
            telegram.send(f"Voice change task {task_id} CRITICAL failure: {error}")
            return {"ok": False, "error": error}


if __name__ == "__main__":
    from shared.queue.config import QUEUE_VOICE
    from shared.queue.worker_runner import main
    main([QUEUE_VOICE], "cff-voice")
