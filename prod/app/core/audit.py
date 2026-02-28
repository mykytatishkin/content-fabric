"""Audit logging for critical actions."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

logger = logging.getLogger("audit")

_log_path = os.environ.get("CFF_AUDIT_LOG", "/var/log/cff-audit.log")
_handler = RotatingFileHandler(
    _log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def log(
    action: str,
    actor_id: int | None = None,
    actor_role: str | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a structured audit log entry."""
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "action": action,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "entity_type": entity_type,
        "entity_id": entity_id,
    }
    if metadata:
        entry["meta"] = metadata
    logger.info(json.dumps(entry, ensure_ascii=False, default=str))
