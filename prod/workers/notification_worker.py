"""Notification worker — rq worker consuming from 'notifications' queue."""

from __future__ import annotations

import logging

from shared.notifications.manager import notify
from shared.queue.types import NotificationPayload

logger = logging.getLogger(__name__)


def send_notification(payload: NotificationPayload) -> bool:
    """Job handler called by rq. Returns True on success."""
    logger.info(
        "Processing notification: channel=%s recipient=%s",
        payload.channel,
        payload.recipient,
    )
    ok = notify(payload)
    if not ok:
        logger.error("Notification delivery failed for %s", payload.recipient)
    return ok


if __name__ == "__main__":
    import shared.env  # noqa: F401 — load .env files

    from rq import Worker

    from shared.queue.config import get_redis, QUEUE_NOTIFICATIONS

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    redis_conn = get_redis()
    worker = Worker([QUEUE_NOTIFICATIONS], connection=redis_conn)
    worker.work()
