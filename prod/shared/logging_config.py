"""Centralized logging configuration with structured JSON output + trace context.

Every log record automatically carries:
  - trace_id  (UUID propagated across worker hops)
  - task_id   (when set by worker)
  - worker    (service name)

Toggle JSON via LOG_FORMAT=json (recommended for production / Loki ingestion).

Side effect: MetricsLogHandler is attached so that every WARNING+ record
becomes a Prometheus counter sample. Gives us real error rates that don't
depend on whether the code re-raises.
"""

from __future__ import annotations

import logging
import os
import sys

from shared.logging_context import TraceContextFilter, get_worker


class MetricsLogHandler(logging.Handler):
    """Mirror every WARNING+ log record into a Prometheus counter.

    Lazy-imports cff metrics module so importing logging_config.py before
    metrics.py is safe (avoids circular imports during early bootstrap).
    """

    LEVEL_MIN = logging.WARNING

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < self.LEVEL_MIN:
                return
            try:
                from shared.metrics import log_events_total
            except Exception:
                return
            log_events_total.labels(
                level=record.levelname,
                logger=record.name[:60],
                worker=get_worker() or "?",
            ).inc()
        except Exception:
            # logging handlers must NEVER raise
            pass


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

    # Mirror WARNING+ records into a Prometheus counter for proper
    # error-rate dashboards. Filter is shared with the main handler so
    # every record gets trace_id labels too.
    metrics_handler = MetricsLogHandler()
    metrics_handler.setLevel(logging.WARNING)
    metrics_handler.addFilter(trace_filter)
    root.addHandler(metrics_handler)

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
