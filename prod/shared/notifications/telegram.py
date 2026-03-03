"""Telegram notification sender."""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

def send(message: str, chat_id: str | None = None) -> bool:
    """Send a Telegram message. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    target = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not target:
        logger.warning("Telegram credentials not configured")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            logger.info("Telegram notification sent")
            return True
        logger.error("Telegram send failed: %s", resp.text)
        return False
    except Exception:
        logger.exception("Telegram send error")
        return False
