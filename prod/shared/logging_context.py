"""Distributed tracing context — propagates trace_id across async boundaries.

Usage:
    # At entry point (FastAPI middleware, worker job start):
    from shared.logging_context import set_trace_id, new_trace_id

    trace_id = payload.metadata.get("trace_id") or new_trace_id()
    set_trace_id(trace_id)

    # In any nested function — automatic via logging filter:
    logger.info("Doing work")  # logs include trace_id=<id>

    # To attach to outgoing payloads:
    payload.metadata["trace_id"] = get_trace_id()
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

# ContextVar is propagated across asyncio tasks and rq job execution.
_trace_id_var: ContextVar[str | None] = ContextVar("cff_trace_id", default=None)
_task_id_var: ContextVar[int | None] = ContextVar("cff_task_id", default=None)
_worker_var: ContextVar[str | None] = ContextVar("cff_worker", default=None)


def new_trace_id() -> str:
    """Generate a new trace identifier (UUID4 hex, 32 chars)."""
    return uuid.uuid4().hex


def set_trace_id(trace_id: str | None) -> None:
    _trace_id_var.set(trace_id)


def get_trace_id() -> str | None:
    return _trace_id_var.get()


def set_task_id(task_id: int | None) -> None:
    _task_id_var.set(task_id)


def get_task_id() -> int | None:
    return _task_id_var.get()


def set_worker(name: str | None) -> None:
    _worker_var.set(name)


def get_worker() -> str | None:
    return _worker_var.get()


def ensure_trace_id() -> str:
    """Return current trace_id, creating one if not set."""
    tid = _trace_id_var.get()
    if not tid:
        tid = new_trace_id()
        _trace_id_var.set(tid)
    return tid


def context_dict() -> dict[str, Any]:
    """Snapshot of all observability context vars (for log/metric labels)."""
    out: dict[str, Any] = {}
    if (v := _trace_id_var.get()) is not None:
        out["trace_id"] = v
    if (v := _task_id_var.get()) is not None:
        out["task_id"] = v
    if (v := _worker_var.get()) is not None:
        out["worker"] = v
    return out


class TraceContextFilter(logging.Filter):
    """Logging filter that injects trace_id / task_id / worker as record attributes.

    Both stdlib formatters (%-style) and pythonjsonlogger pick these up automatically:
        plain:  %(trace_id)s
        json:   {"trace_id": "..."}
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id_var.get() or "-"
        record.task_id = _task_id_var.get() if _task_id_var.get() is not None else "-"
        record.worker = _worker_var.get() or "-"
        return True
