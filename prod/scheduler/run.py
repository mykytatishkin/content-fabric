"""Scheduler entry point — polls DB every 60s for pending tasks."""

from __future__ import annotations

import logging
import signal
import time

from scheduler.jobs import enqueue_pending_tasks

POLL_INTERVAL = 60  # seconds

logger = logging.getLogger(__name__)
_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down scheduler...", signum)
    _running = False


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Scheduler started — polling every %ds", POLL_INTERVAL)

    while _running:
        try:
            count = enqueue_pending_tasks()
            if count:
                logger.info("Enqueued %d task(s) this cycle", count)
        except Exception:
            logger.exception("Scheduler cycle failed")

        # Sleep in small increments to allow graceful shutdown
        for _ in range(POLL_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
