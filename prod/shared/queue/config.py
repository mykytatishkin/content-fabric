"""Redis connection configuration."""

from __future__ import annotations

import logging
import os

from redis import Redis

logger = logging.getLogger(__name__)

_redis: Redis | None = None

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Queue names
QUEUE_PUBLISHING = "publishing"
QUEUE_NOTIFICATIONS = "notifications"
QUEUE_VOICE = "voice"


def get_redis() -> Redis:
    """Get or create the global Redis connection."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL, decode_responses=False)
        logger.info("Redis connection established: %s", REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL)
    return _redis


def close_redis() -> None:
    """Close Redis connection (for shutdown)."""
    global _redis
    if _redis is not None:
        _redis.close()
        _redis = None
        logger.info("Redis connection closed")
