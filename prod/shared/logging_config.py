"""Centralized logging configuration with structured JSON output + trace context.

Every log record automatically carries:
  - trace_id  (UUID propagated across worker hops)
  - task_id   (when set by worker)
  - worker    (service name)

Toggle JSON via LOG_FORMAT=json (recommended for production / Loki ingestion).
"""

from __future__ import annotations

import logging
import os
import sys

from shared.logging_context import TraceContextFilter


_JSON_EXTRA_FIELDS = ["trace_id", "task_id", "worker"]


def _build_json_formatter() -> logging.Formatter:
    """JSON formatter with extra trace context fields."""
    from pythonjsonlogger import jsonlogger

    fmt = "%(asctime)s %(name)s %(levelname)s %(message)s " + " ".join(f"%({f})s" for f in _JSON_EXTRA_FIELDS)
    formatter = jsonlogger.JsonFormatter(
        fmt=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    formatter.default_msec_format = "%s.%03d"
    return formatter


def _build_text_formatter() -> logging.Formatter:
    """Plain text formatter — trace_id appended at the end of each line."""
    return logging.Formatter(
        fmt="%(asctime)s %(name)s %(levelname)s [trace=%(trace_id)s task=%(task_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def setup_logging(service_name: str = "cff") -> None:
    level_name = os.environ.get("LOG_LEVEL", "DEBUG" if os.environ.get("DEBUG") == "1" else "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    use_json = os.environ.get("LOG_FORMAT", "").lower() == "json"

    root = logging.getLogger()
    root.setLevel(level)

    # Replace handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Trace context filter — attached at handler level so every record
    # passes through it before formatting (works for both stdlib and json).
    trace_filter = TraceContextFilter()
    handler.addFilter(trace_filter)

    if use_json:
        try:
            formatter = _build_json_formatter()
        except ImportError:
            formatter = _build_text_formatter()
    else:
        formatter = _build_text_formatter()

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Quiet noisy libraries
    for name in ("urllib3", "sqlalchemy.engine", "googleapiclient", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger(service_name).info(
        "Logging initialized: level=%s json=%s service=%s",
        level_name, use_json, service_name,
    )

    # Set worker name in context so all records from this service carry it.
    from shared.logging_context import set_worker
    set_worker(service_name)
