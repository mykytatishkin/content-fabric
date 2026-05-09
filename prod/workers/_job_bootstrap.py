"""Common bootstrap helper for all rq workers.

Each job handler should call `bootstrap_job(payload, worker_name)` at the very
top — this attaches trace_id and task_id to the logging context so every log
line emitted while processing this job is automatically labeled.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.logging_context import (
    new_trace_id,
    set_task_id,
    set_trace_id,
    set_worker,
)

logger = logging.getLogger(__name__)


def bootstrap_job(payload: Any, worker_name: str) -> str:
    """Pull trace_id from payload (or create one) and bind to logging context.

    Args:
        payload: any dataclass with optional `trace_id` and `task_id` attrs.
        worker_name: stable identifier of the worker (cff-dle-ingestion, etc.).

    Returns:
        The active trace_id (always non-empty).
    """
    set_worker(worker_name)

    tid = getattr(payload, "trace_id", None)
    if not tid:
        tid = new_trace_id()
        try:
            setattr(payload, "trace_id", tid)
        except Exception:
            pass
    set_trace_id(tid)

    task_id = getattr(payload, "task_id", None)
    if task_id is not None:
        set_task_id(int(task_id))

    logger.info("[%s] BOOTSTRAP trace_id=%s task_id=%s payload=%s",
                worker_name, tid, task_id, type(payload).__name__)
    return tid
