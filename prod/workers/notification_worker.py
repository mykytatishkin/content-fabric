"""Notification worker — rq worker consuming from 'notifications' queue."""

from __future__ import annotations

import logging

from shared.metrics import instrument_job
from shared.notifications.manager import notify
from shared.queue.types import NotificationPayload
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


@instrument_job("notification")
def send_notification(payload: NotificationPayload) -> bool:
    """Job handler called by rq. Returns True on success."""
    bootstrap_job(payload, "cff-notification")
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
    from shared.queue.config import QUEUE_NOTIFICATIONS
    from shared.queue.worker_runner import main
    main([QUEUE_NOTIFICATIONS], "cff-notification")
