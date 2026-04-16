"""Scheduler entry point — polls DB every 60s for pending tasks."""

from __future__ import annotations

import logging
import signal
import time
from datetime import date

import shared.env  # noqa: F401 — load .env files before anything else

from scheduler.jobs import enqueue_pending_tasks, validate_channel_tokens, collect_channel_stats, collect_video_stats
from shared.logging_config import setup_logging

POLL_INTERVAL = 60  # seconds

logger = logging.getLogger(__name__)
_running = True


def _handle_signal(signum, frame):
    global _running
    logger.info("Received signal %d, shutting down scheduler...", signum)
    _running = False


def main() -> None:
    setup_logging(service_name="cff-scheduler")
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Scheduler started — polling every %ds", POLL_INTERVAL)

    last_token_check_date: date | None = None
    last_stats_date: date | None = None

    while _running:
        try:
            count = enqueue_pending_tasks()
            if count:
                logger.info("Enqueued %d task(s) this cycle", count)
        except Exception:
            logger.exception("Scheduler cycle failed")

        # Daily token validation — run once per calendar day
        today = date.today()
        if last_token_check_date != today:
            try:
                logger.info("Running daily token validation...")
                ok, fail = validate_channel_tokens()
                last_token_check_date = today
                logger.info("Daily token validation done: %d ok, %d failed", ok, fail)
            except Exception:
                logger.exception("Daily token validation failed")

        # Daily stats collection — run once per calendar day
        if last_stats_date != today:
            try:
                logger.info("Running daily channel stats collection...")
                ok, fail = collect_channel_stats()
                logger.info("Channel stats done: %d ok, %d failed", ok, fail)
            except Exception:
                logger.exception("Daily channel stats collection failed")

            try:
                logger.info("Running daily video stats collection...")
                ok, fail = collect_video_stats()
                logger.info("Video stats done: %d ok, %d failed", ok, fail)
            except Exception:
                logger.exception("Daily video stats collection failed")

            last_stats_date = today

        # Sleep in small increments to allow graceful shutdown
        for _ in range(POLL_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
