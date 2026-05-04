"""DLE Processor Worker — обробка завдань DLE (скачування → voice → відео)."""

import logging
import os
from typing import Any

from rq import Worker
from rq.job import JobStatus

from shared.db.connection import get_connection
from shared.db.repositories.task_repo import get_task, update_task
from shared.ingestion.dle.processor import DleProcessor
from shared.notifications.manager import send_notification
from shared.queue.config import get_redis_connection
from shared.queue.types import DleProcessingPayload

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Обробник для консолі
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def process_dle_task(payload: DleProcessingPayload) -> dict[str, Any]:
    """Обробити DLE завдання: скачати → обробити → зберегти шлях."""
    task_id = payload.task_id
    logger.info("[DLE PROCESSOR WORKER] START task_id=%s", task_id)

    try:
        # Отримати завдання з БД
        with get_connection() as conn:
            task = get_task(conn, task_id)
            if not task:
                logger.error("[DLE PROCESSOR WORKER] Task %s not found", task_id)
                return {"status": "error", "message": "Task not found"}

        logger.info("[DLE PROCESSOR WORKER] Processing task %s: %s", task_id, task.get("title"))

        # Обробити через DleProcessor
        processor = DleProcessor(work_dir="/tmp/dle_processing")
        final_video_path = processor.process_task(task)

        if not final_video_path:
            logger.error("[DLE PROCESSOR WORKER] Processor returned None for task %s", task_id)
            with get_connection() as conn:
                update_task(conn, task_id, {
                    "status": "error",
                    "error_message": "DLE processor failed to generate video"
                })
            send_notification(
                f"❌ DLE Processor Error\nTask {task_id}: {task.get('title')}\nFailed to generate video"
            )
            return {"status": "error", "message": "Processor failed"}

        logger.info("[DLE PROCESSOR WORKER] Video ready: %s", final_video_path)

        # Оновити завдання з шляхом до файлу
        with get_connection() as conn:
            update_task(conn, task_id, {
                "source_file_path": final_video_path,
                "status": "pending"  # Готово до публікації
            })

        logger.info("[DLE PROCESSOR WORKER] Task %s updated with video path", task_id)
        send_notification(f"✅ DLE Video Ready\nTask {task_id}: {task.get('title')}")

        return {
            "status": "success",
            "task_id": task_id,
            "video_path": final_video_path
        }

    except Exception as exc:
        logger.exception("[DLE PROCESSOR WORKER] EXCEPTION for task %s: %s", task_id, exc)
        try:
            with get_connection() as conn:
                update_task(conn, task_id, {
                    "status": "error",
                    "error_message": f"DLE processor exception: {str(exc)[:500]}"
                })
        except Exception as db_exc:
            logger.error("[DLE PROCESSOR WORKER] Failed to update task status: %s", db_exc)

        send_notification(f"❌ DLE Processor Exception\nTask {task_id}: {str(exc)[:200]}")
        return {"status": "error", "message": str(exc)}


def main():
    """Запустити worker для обробки DLE завдань."""
    redis_conn = get_redis_connection()
    worker = Worker(["dle_processing"], connection=redis_conn)
    logger.info("[DLE PROCESSOR WORKER] Starting worker on queue 'dle_processing'")
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
