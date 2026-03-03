"""Notification manager — facade for Telegram + Email."""

from __future__ import annotations

import logging

from shared.notifications import telegram, email as email_mod
from shared.queue.types import NotificationPayload

logger = logging.getLogger(__name__)


def notify(payload: NotificationPayload) -> bool:
    """Route notification to the correct channel."""
    channel = payload.channel.lower()
    if channel == "telegram":
        return telegram.send(
            message=payload.message,
            chat_id=payload.recipient or None,
        )
    elif channel == "email":
        recipients = [r.strip() for r in payload.recipient.split(",") if r.strip()]
        return email_mod.send(
            recipients=recipients,
            subject=payload.subject or "Content Fabric Notification",
            body=payload.message,
        )
    else:
        logger.error("Unknown notification channel: %s", channel)
        return False
