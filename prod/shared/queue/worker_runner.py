"""Common runner for rq workers.

Wraps `worker.work()` so that Redis failover errors raised during teardown
(`register_death`, `SREM rq:workers ...`) do not propagate as crash tracebacks.

When the Redis primary is demoted to a replica mid-shutdown, the pipeline
flush issues a write that the replica refuses with `ReadOnlyError`, and the
worker exits 1. systemd then escalates the restart counter and the journal
fills with tracebacks. We catch the narrow set of "this is normal during
failover" exceptions, log a warning, and exit 0 — systemd still restarts
the unit (Restart=always) and the next process picks up the new primary.

We deliberately do NOT swallow arbitrary exceptions. Only the specific
Redis classes triggered by failover are silenced.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Iterable

logger = logging.getLogger(__name__)


# Redis exception classes that indicate "primary failed over to replica"
# rather than a real error in our code. They are imported lazily so that
# tests which mock the redis module still work.
def _failover_exceptions() -> tuple[type[BaseException], ...]:
    try:
        from redis.exceptions import (
            ReadOnlyError,
            ResponseError,
            ConnectionError as RedisConnectionError,
        )
    except Exception:  # pragma: no cover — redis must be installed in prod
        return ()
    return (ReadOnlyError, ResponseError, RedisConnectionError)


def run_worker(queues: Iterable[str], connection: Any, service_name: str) -> int:
    """Start an rq Worker on the given queues, gracefully handling failover.

    Returns:
        Exit code suitable for `sys.exit()` (0 on graceful shutdown, 1 on
        unexpected errors).
    """
    from rq import Worker

    worker = Worker(list(queues), connection=connection)
    failover_excs = _failover_exceptions()

    try:
        worker.work()
        return 0
    except failover_excs as exc:  # type: ignore[misc]
        # Distinguish "real" ResponseError from failover ResponseError.
        # Failover messages contain "UNBLOCKED", "READONLY", or
        # "read only replica".
        msg = str(exc).lower()
        is_failover = (
            "unblocked" in msg
            or "readonly" in msg
            or "read only replica" in msg
            or "loading" in msg            # Redis startup
            or "master_link_status" in msg
        )
        if is_failover:
            logger.warning(
                "[%s] Redis failover detected during teardown (%s: %s); "
                "exiting cleanly so systemd restarts on the new primary.",
                service_name, type(exc).__name__, exc,
            )
            return 0
        logger.exception("[%s] Unhandled Redis error: %s", service_name, exc)
        return 1


def main(queues: Iterable[str], service_name: str) -> None:
    """Convenience entrypoint used from `if __name__ == '__main__'` blocks."""
    import shared.env  # noqa: F401 — load .env files

    from shared.logging_config import setup_logging
    from shared.queue.config import get_redis

    setup_logging(service_name=service_name)
    sys.exit(run_worker(queues, get_redis(), service_name))
