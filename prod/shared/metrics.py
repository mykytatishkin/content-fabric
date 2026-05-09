"""Prometheus metrics for CFF — counters, histograms, gauges + push helper.

Two collection patterns:

1. Long-running services (cff-api) expose `/metrics` and Prometheus scrapes
   them every 15s. Use the module-level objects directly:

       from shared.metrics import tasks_total
       tasks_total.labels(status="completed", channel="42").inc()

2. Short-lived rq jobs would die before being scraped. They push to the
   pushgateway with `push_job_metrics(job_name, labels, registry)`:

       from shared.metrics import push_job_metrics, job_registry, job_duration
       reg = job_registry()
       hist = job_duration(reg, "dle_processor")
       with hist.time():
           ... do the work ...
       push_job_metrics("dle_processor", {"channel": "42"}, reg)

The instrument_job() decorator does this boilerplate automatically.
"""

from __future__ import annotations

import functools
import logging
import os
import time
from typing import Any, Callable

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    REGISTRY,
)
from prometheus_client.exposition import push_to_gateway

logger = logging.getLogger(__name__)

PUSHGATEWAY_URL = os.environ.get("PUSHGATEWAY_URL", "http://127.0.0.1:9091")


# ─── App-level metrics (registered to the default REGISTRY) ─────────

# Histogram buckets tuned for our pipeline:
# fast queries ≤100ms, normal API <1s, voice change minutes, ffmpeg/upload longer.
_DURATION_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 180, 600, 1800, 3600)

# Tasks
tasks_created_total = Counter(
    "cff_tasks_created_total",
    "Tasks inserted into content_upload_queue_tasks.",
    ["source", "media_type", "channel"],
)
tasks_completed_total = Counter(
    "cff_tasks_completed_total",
    "Tasks reaching status=completed (uploaded to YouTube).",
    ["channel"],
)
tasks_failed_total = Counter(
    "cff_tasks_failed_total",
    "Tasks reaching status=failed.",
    ["channel", "stage", "error_kind"],
)

# Stage timings — one observation per pipeline stage
task_stage_duration_seconds = Histogram(
    "cff_task_stage_duration_seconds",
    "Time spent in a pipeline stage for one task.",
    ["stage"],          # ingestion | processing | voice | upload | publish
    buckets=_DURATION_BUCKETS,
)

# Queue depth — sampled by /metrics scrape
queue_depth = Gauge(
    "cff_queue_depth",
    "Number of jobs waiting in an rq queue.",
    ["queue"],
)

# DLE source health
dle_source_up = Gauge(
    "cff_dle_source_up",
    "1 if the DLE source MySQL responded to SELECT 1, else 0.",
    ["source"],
)
dle_source_check_duration_seconds = Histogram(
    "cff_dle_source_check_duration_seconds",
    "How long the periodic SELECT 1 connection check took.",
    ["source"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

# YouTube
youtube_token_expires_in_seconds = Gauge(
    "cff_youtube_token_expires_in_seconds",
    "Seconds until OAuth token for a channel expires (negative = expired).",
    ["channel"],
)
youtube_upload_bytes = Histogram(
    "cff_youtube_upload_bytes",
    "Size in bytes of videos pushed to YouTube.",
    ["channel"],
    buckets=(1e6, 10e6, 100e6, 500e6, 1e9, 5e9, 10e9),
)
youtube_upload_duration_seconds = Histogram(
    "cff_youtube_upload_duration_seconds",
    "Time spent in resumable upload.",
    ["channel"],
    buckets=_DURATION_BUCKETS,
)

# Streams
stream_active = Gauge(
    "cff_stream_active",
    "1 if systemd stream-* is active+running, else 0.",
    ["stream", "service"],
)
stream_uptime_seconds = Gauge(
    "cff_stream_uptime_seconds",
    "Seconds since the stream-* unit became active.",
    ["stream"],
)

# HTTP errors / app exceptions
errors_total = Counter(
    "cff_errors_total",
    "Errors logged by CFF code (excluding 4xx HTTP).",
    ["worker", "error_kind"],
)

# Every log record above WARNING goes here too via MetricsLogHandler.
# Lets us compute real error rates without depending on `raise`.
log_events_total = Counter(
    "cff_log_events_total",
    "Total log records emitted, by level/logger/worker.",
    ["level", "logger", "worker"],
)
# Pre-warm labels so the metric appears in /metrics from the start with 0,
# rather than only after the first WARNING fires.
for _lvl in ("WARNING", "ERROR", "CRITICAL"):
    log_events_total.labels(level=_lvl, logger="-", worker="-")

# DB-backed gauges — sample_all() refreshes these from MySQL every 30s.
# Useful even when Counter-based metrics are stuck at 0 (no new traffic yet).
tasks_in_status = Gauge(
    "cff_tasks_in_status",
    "Current count of content_upload_queue_tasks rows by status.",
    ["status"],   # pending|completed|failed|processing|cancelled
)
tasks_created_recent = Gauge(
    "cff_tasks_created_recent",
    "Tasks inserted within the last N minutes (by window).",
    ["window"],   # 1h|24h
)
tasks_completed_recent = Gauge(
    "cff_tasks_completed_recent",
    "Tasks reaching status=completed within the last N minutes.",
    ["window"],
)
tasks_failed_recent = Gauge(
    "cff_tasks_failed_recent",
    "Tasks reaching status=failed within the last N minutes.",
    ["window"],
)
streams_in_state = Gauge(
    "cff_streams_in_state",
    "Live stream systemd units grouped by state.",
    ["state"],   # active_running | inactive_dead | failed | activating
)

build_info = Info(
    "cff_build",
    "Static build/version info (filled at startup).",
)


# ─── Pushgateway helpers (for short-lived workers) ──────────────────


def job_registry() -> CollectorRegistry:
    """Fresh registry per job — keeps push payload small + isolated."""
    return CollectorRegistry()


def job_duration(registry: CollectorRegistry, worker: str) -> Histogram:
    return Histogram(
        f"cff_worker_job_duration_seconds",
        "Per-job execution time.",
        ["worker", "outcome"],
        buckets=_DURATION_BUCKETS,
        registry=registry,
    ).labels(worker=worker, outcome="ok")


def push_job_metrics(job_name: str, grouping: dict[str, str], registry: CollectorRegistry) -> None:
    """Send the registry to pushgateway. Errors are logged, never raised."""
    try:
        push_to_gateway(
            PUSHGATEWAY_URL,
            job=job_name,
            registry=registry,
            grouping_key=grouping,
            timeout=5,
        )
    except Exception as exc:
        logger.debug("Pushgateway send failed for %s: %s", job_name, exc)


# ─── Decorator for rq job handlers ──────────────────────────────────


def instrument_job(worker_name: str) -> Callable:
    """Wrap an rq job handler with timing + outcome metric → pushgateway.

    Usage:
        @instrument_job("dle_processor")
        def process_dle_task(payload): ...
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            registry = CollectorRegistry()
            hist = Histogram(
                "cff_worker_job_duration_seconds",
                "Per-job execution time.",
                ["worker", "outcome"],
                buckets=_DURATION_BUCKETS,
                registry=registry,
            )
            counter = Counter(
                "cff_worker_jobs_total",
                "Per-job invocation count.",
                ["worker", "outcome"],
                registry=registry,
            )
            outcome = "ok"
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                # If the handler returned a dict with ok=False, treat as fail
                if isinstance(result, dict) and result.get("ok") is False:
                    outcome = "fail"
                return result
            except Exception:
                outcome = "exception"
                errors_total.labels(worker=worker_name, error_kind="exception").inc()
                raise
            finally:
                elapsed = time.monotonic() - start
                hist.labels(worker=worker_name, outcome=outcome).observe(elapsed)
                counter.labels(worker=worker_name, outcome=outcome).inc()
                # task_id is the natural grouping_key — instances grouped per task
                grouping: dict[str, str] = {}
                if args:
                    payload = args[0]
                    tid = getattr(payload, "task_id", None)
                    if tid is not None:
                        grouping["task_id"] = str(tid)
                push_job_metrics(f"cff-{worker_name}", grouping, registry)

        return wrapper
    return decorator


# ─── Sampled metrics — call from a periodic task in the scheduler ───


def sample_queue_depths() -> None:
    """Update queue_depth gauges by reading rq queue lengths from Redis."""
    try:
        from shared.queue.config import get_redis
        r = get_redis()
        for q in ["publishing", "notifications", "voice", "dle_ingestion",
                  "dle_processing", "shorts", "sora", "stats", "stream_control"]:
            try:
                length = int(r.llen(f"rq:queue:{q}"))
            except Exception:
                length = 0
            queue_depth.labels(queue=q).set(length)
    except Exception as exc:
        logger.debug("sample_queue_depths failed: %s", exc)


def sample_dle_source_health() -> None:
    """Quick SELECT 1 against each DLE DSN, update dle_source_up."""
    try:
        from app.core.config import dle_settings
        from sqlalchemy import create_engine, text
        for slug, dsn in dle_settings.all_sources().items():
            t0 = time.monotonic()
            ok = 0.0
            try:
                eng = create_engine(dsn, connect_args={"connect_timeout": 5})
                with eng.connect() as conn:
                    conn.execute(text("SELECT 1"))
                ok = 1.0
                eng.dispose()
            except Exception:
                ok = 0.0
            elapsed = time.monotonic() - t0
            dle_source_up.labels(source=slug).set(ok)
            dle_source_check_duration_seconds.labels(source=slug).observe(elapsed)
    except Exception as exc:
        logger.debug("sample_dle_source_health failed: %s", exc)


def sample_youtube_token_expiries() -> None:
    """Read token_expires_at from platform_channels, update gauge."""
    try:
        from shared.db.connection import get_connection
        from sqlalchemy import text
        now = time.time()
        with get_connection() as conn:
            rows = conn.execute(text("""
                SELECT name, token_expires_at
                FROM platform_channels
                WHERE platform = 'youtube' AND enabled = 1 AND access_token IS NOT NULL
            """)).fetchall()
        for r in rows:
            name, expires = r
            if expires is None:
                continue
            try:
                ts = expires.timestamp()
            except AttributeError:
                continue
            youtube_token_expires_in_seconds.labels(channel=str(name)).set(ts - now)
    except Exception as exc:
        logger.debug("sample_youtube_token_expiries failed: %s", exc)


def sample_stream_status() -> None:
    """Use systemctl to update stream_active + stream_uptime gauges."""
    import subprocess
    try:
        r = subprocess.run(
            ["systemctl", "list-units", "stream-*.service", "--no-legend",
             "--no-pager", "--all"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.strip().splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit = parts[0].lstrip("●").strip()
            if not unit.endswith(".service"):
                continue
            stream_name = unit.removesuffix(".service").removeprefix("stream-")
            sub_state = parts[3] if len(parts) > 3 else ""
            active = 1.0 if sub_state == "running" else 0.0
            stream_active.labels(stream=stream_name, service=unit).set(active)

            # Uptime via systemctl show
            try:
                r2 = subprocess.run(
                    ["systemctl", "show", unit,
                     "--property=ActiveEnterTimestampMonotonic"],
                    capture_output=True, text=True, timeout=3,
                )
                # value in microseconds since boot
                line2 = r2.stdout.strip()
                if "=" in line2:
                    monotonic = int(line2.split("=", 1)[1] or 0)
                    if monotonic > 0:
                        # Compute "now monotonic" via /proc/uptime
                        with open("/proc/uptime", "r", encoding="utf-8") as f:
                            up = float(f.read().split()[0])
                        uptime = max(0.0, up - monotonic / 1_000_000.0)
                        stream_uptime_seconds.labels(stream=stream_name).set(uptime)
            except Exception:
                pass
    except Exception as exc:
        logger.debug("sample_stream_status failed: %s", exc)


def sample_db_task_counts() -> None:
    """Read current task distribution from MySQL — fills tasks_in_status + recent windows."""
    try:
        from shared.db.connection import get_connection
        from sqlalchemy import text

        status_names = {0: "pending", 1: "completed", 2: "failed",
                         3: "processing", 4: "cancelled"}

        with get_connection() as conn:
            # By-status totals
            rows = conn.execute(text(
                "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
            )).fetchall()
            seen: set[str] = set()
            for status_int, cnt in rows:
                name = status_names.get(int(status_int), f"unknown_{status_int}")
                tasks_in_status.labels(status=name).set(int(cnt))
                seen.add(name)
            # Zero out missing statuses so gauges don't hold stale values
            for name in set(status_names.values()) - seen:
                tasks_in_status.labels(status=name).set(0)

            # Sliding windows (created in last hour / day)
            for window, hours in (("1h", 1), ("24h", 24)):
                row = conn.execute(text(f"""
                    SELECT
                        SUM(CASE WHEN created_at >= NOW() - INTERVAL :h HOUR THEN 1 ELSE 0 END) as created,
                        SUM(CASE WHEN status = 1 AND completed_at >= NOW() - INTERVAL :h HOUR THEN 1 ELSE 0 END) as completed,
                        SUM(CASE WHEN status = 2 AND completed_at >= NOW() - INTERVAL :h HOUR THEN 1 ELSE 0 END) as failed
                    FROM content_upload_queue_tasks
                """), {"h": hours}).fetchone()
                tasks_created_recent.labels(window=window).set(int(row[0] or 0))
                tasks_completed_recent.labels(window=window).set(int(row[1] or 0))
                tasks_failed_recent.labels(window=window).set(int(row[2] or 0))
    except Exception as exc:
        logger.debug("sample_db_task_counts failed: %s", exc)


def sample_stream_state_counts() -> None:
    """Aggregate stream_active gauge into streams_in_state by sub-state."""
    import subprocess
    counts = {"active_running": 0, "inactive_dead": 0, "failed": 0, "activating": 0}
    try:
        r = subprocess.run(
            ["systemctl", "list-units", "stream-*.service", "--no-legend",
             "--no-pager", "--all"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.strip().splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            unit = parts[0].lstrip("●").strip()
            if not unit.endswith(".service"):
                continue
            active = parts[2] if len(parts) > 2 else ""
            sub = parts[3] if len(parts) > 3 else ""
            key = f"{active}_{sub}".lower()
            if key in counts:
                counts[key] += 1
            elif sub == "running":
                counts["active_running"] += 1
            elif sub == "dead":
                counts["inactive_dead"] += 1
            elif active == "failed":
                counts["failed"] += 1
            elif active == "activating":
                counts["activating"] += 1
        for state, n in counts.items():
            streams_in_state.labels(state=state).set(n)
    except Exception as exc:
        logger.debug("sample_stream_state_counts failed: %s", exc)


def sample_all() -> None:
    """Single entry point — call from scheduler/run.py loop or a periodic task."""
    sample_queue_depths()
    sample_dle_source_health()
    sample_youtube_token_expiries()
    sample_stream_status()
    sample_db_task_counts()
    sample_stream_state_counts()
