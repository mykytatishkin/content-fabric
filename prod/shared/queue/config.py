"""Redis connection configuration."""

from __future__ import annotations

import logging
import os

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from redis.retry import Retry

logger = logging.getLogger(__name__)

_redis: Redis | None = None

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# Periodic PING to detect dead/demoted connections. Tunable via env so we can
# tighten it during incidents without a redeploy.
REDIS_HEALTH_CHECK_INTERVAL = int(os.environ.get("REDIS_HEALTH_CHECK_INTERVAL", "30"))
REDIS_RETRY_ATTEMPTS = int(os.environ.get("REDIS_RETRY_ATTEMPTS", "3"))

# Queue names
QUEUE_PUBLISHING = "publishing"
QUEUE_NOTIFICATIONS = "notifications"
QUEUE_VOICE = "voice"

# Queues from Yii migration (feat/yii-integration)
QUEUE_DLE_INGESTION = "dle_ingestion"      # Парсинг 7 DLE-сайтов → создание задач
QUEUE_SHORTS = "shorts"                     # YouTube Shorts pipeline (yt-dlp + Whisper + GPT)
QUEUE_SORA = "sora"                         # Sora AI scraping через zenrows
QUEUE_STATS = "stats"                       # Daily YouTube channel statistics
QUEUE_STREAM_CONTROL = "stream_control"     # Управление 9 RTMP стримами через systemd


def get_redis() -> Redis:
    """Get or create the global Redis connection.

    Retry + health-check are enabled so transient ConnectionError/TimeoutError
    (e.g. during a Redis primary failover) are swallowed at the client layer
    instead of bubbling up as crash tracebacks. Note: ReadOnlyError is NOT
    retried — that's handled in shared.queue.worker_runner.run_worker because
    it indicates the connection is bound to a stale primary and must be
    re-established by a worker restart.
    """
    global _redis
    if _redis is None:
        retry = Retry(ExponentialBackoff(cap=10, base=1), REDIS_RETRY_ATTEMPTS)
        _redis = Redis.from_url(
            REDIS_URL,
            decode_responses=False,
            health_check_interval=REDIS_HEALTH_CHECK_INTERVAL,
            socket_keepalive=True,
            retry=retry,
            retry_on_error=[RedisConnectionError, RedisTimeoutError],
        )
        logger.info(
            "Redis connection established: %s (retry=%d, health_check=%ds)",
            REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL,
            REDIS_RETRY_ATTEMPTS,
            REDIS_HEALTH_CHECK_INTERVAL,
        )
    return _redis


def close_redis() -> None:
    """Close Redis connection (for shutdown)."""
    global _redis
    if _redis is not None:
        _redis.close()
        _redis = None
        logger.info("Redis connection closed")
