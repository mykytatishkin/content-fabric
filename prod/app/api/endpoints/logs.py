"""AI-friendly Logs API.

Endpoints designed for both humans (via /panel/logs UI) and machine clients
(other Claude sessions, CI scripts, monitoring agents):

    GET  /api/v1/logs/services            → list of all journald units we know
    GET  /api/v1/logs                     → filtered list (service, level, time, query)
    GET  /api/v1/logs/trace/{trace_id}    → all entries for a single task across services
    GET  /api/v1/logs/tail/{service}      → last N lines of one service
    GET  /api/v1/logs/analyze             → summary: top errors, error rate per service,
                                            anomaly hints, hot trace_ids
    GET  /api/v1/logs/stats               → counts by level/service over time window

Every response is JSON. Logs are parsed from `journalctl --output=json` so we
get structured fields (timestamp, message, priority, _SYSTEMD_UNIT, etc.) and
post-process them to extract our own annotations (trace_id, task_id) from the
text.

Auth: same as other API endpoints (Depends get_current_user).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Known services ──────────────────────────────────────────────────

KNOWN_CFF_SERVICES = [
    "cff-api",
    "cff-scheduler",
    "cff-publishing-worker",
    "cff-notification-worker",
    "cff-voice-worker",
    "cff-dle-ingestion-worker",
    "cff-dle-processor-worker",
    "cff-shorts-worker",
    "cff-stats-worker",
    "cff-stream-control-worker",
]

KNOWN_STREAM_PREFIX = "stream-"

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Patterns to extract context from log message text
_TRACE_PATTERN = re.compile(r"(?:trace_id|trace)[=: ]([0-9a-f]{16,32})", re.IGNORECASE)
_TASK_PATTERN = re.compile(r"(?:task_id|task)[=: ](\d+)", re.IGNORECASE)
_LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b")

# journalctl PRIORITY → our level
_PRIORITY_MAP = {
    "0": "EMERG", "1": "ALERT", "2": "CRITICAL", "3": "ERROR",
    "4": "WARNING", "5": "NOTICE", "6": "INFO", "7": "DEBUG",
}


# ─── Helpers ─────────────────────────────────────────────────────────


def _list_stream_units() -> list[str]:
    """Discover stream-* systemd units currently loaded."""
    try:
        r = subprocess.run(
            ["systemctl", "list-unit-files", "stream-*.service", "--no-legend",
             "--no-pager", "--state=enabled,disabled"],
            capture_output=True, text=True, timeout=5,
        )
        units = []
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if parts and parts[0].endswith(".service"):
                units.append(parts[0].removesuffix(".service"))
        return sorted(set(units))
    except Exception:
        return []


def _parse_log_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a journalctl JSON entry into our normalized format.

    journalctl gives us: __REALTIME_TIMESTAMP, MESSAGE, PRIORITY, _SYSTEMD_UNIT,
    SYSLOG_IDENTIFIER, _PID, etc. We normalize and also try to lift trace_id /
    task_id / our app-level level out of the MESSAGE body.
    """
    ts_us = raw.get("__REALTIME_TIMESTAMP")
    if ts_us:
        try:
            ts = datetime.fromtimestamp(int(ts_us) / 1_000_000, tz=timezone.utc)
            iso = ts.isoformat()
        except Exception:
            iso = None
    else:
        iso = None

    message = raw.get("MESSAGE", "") or ""
    if isinstance(message, list):
        # journalctl returns binary blobs as a list of ints — best-effort decode
        try:
            message = bytes(message).decode("utf-8", errors="replace")
        except Exception:
            message = str(message)

    syslog_priority = str(raw.get("PRIORITY", "6"))
    syslog_level = _PRIORITY_MAP.get(syslog_priority, "INFO")

    # Pull app-level level from the message itself (Python logging adds it)
    app_level = None
    m = _LEVEL_PATTERN.search(message[:200])
    if m:
        lv = m.group(1).upper()
        app_level = "WARNING" if lv == "WARN" else ("CRITICAL" if lv == "FATAL" else lv)
    level = app_level or syslog_level

    unit = raw.get("_SYSTEMD_UNIT", "") or raw.get("SYSLOG_IDENTIFIER", "")
    if unit.endswith(".service"):
        unit = unit.removesuffix(".service")

    trace_match = _TRACE_PATTERN.search(message)
    task_match = _TASK_PATTERN.search(message)

    return {
        "timestamp": iso,
        "level": level,
        "service": unit,
        "message": message,
        "trace_id": trace_match.group(1) if trace_match else None,
        "task_id": int(task_match.group(1)) if task_match else None,
        "pid": int(raw["_PID"]) if raw.get("_PID") else None,
        "host": raw.get("_HOSTNAME"),
    }


def _journal_query(
    services: list[str] | None,
    since: str | None = None,
    until: str | None = None,
    grep: str | None = None,
    priority: str | None = None,
    lines: int = 200,
) -> list[dict[str, Any]]:
    """Run journalctl with --output=json and return parsed entries (most recent last)."""
    cmd: list[str] = ["journalctl", "--no-pager", "--output=json", "-n", str(int(lines))]
    for svc in services or []:
        cmd.extend(["-u", f"{svc}.service"])
    if since:
        cmd.extend(["--since", since])
    if until:
        cmd.extend(["--until", until])
    if grep:
        cmd.extend(["-g", grep])
    if priority:
        cmd.extend(["-p", priority])

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return []
    except FileNotFoundError:
        return []

    entries: list[dict[str, Any]] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except Exception:
            continue
        entries.append(_parse_log_entry(raw))
    return entries


# ─── Endpoints ───────────────────────────────────────────────────────


@router.get("/services")
async def list_services(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """Discoverable list of all log sources we expose."""
    streams = _list_stream_units()
    return {
        "cff_services": KNOWN_CFF_SERVICES,
        "stream_services": streams,
        "all": KNOWN_CFF_SERVICES + streams,
    }


@router.get("/")
async def list_logs(
    service: list[str] | None = Query(None, description="Service slug (without .service). Repeat for multiple."),
    level: str | None = Query(None, description=f"Min level filter: one of {','.join(LEVELS)}"),
    since: str | None = Query(None, description="journalctl --since (e.g. '10 min ago', '2026-05-07 12:00')"),
    until: str | None = Query(None, description="journalctl --until"),
    grep: str | None = Query(None, description="Substring filter (regex)"),
    trace_id: str | None = Query(None, description="Filter by trace_id"),
    task_id: int | None = Query(None, description="Filter by task_id"),
    limit: int = Query(200, ge=1, le=5000),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Filtered log query.

    The result is shaped for AI consumption:
        - timestamp ISO 8601 UTC
        - extracted trace_id / task_id when present
        - level normalized to WARNING/ERROR/INFO/DEBUG
    """
    services = service or (KNOWN_CFF_SERVICES + _list_stream_units())

    # journalctl priority filter — pre-cut at syslog level (cheap)
    pri = None
    if level:
        lv = level.upper()
        if lv == "ERROR":
            pri = "err"
        elif lv == "WARNING":
            pri = "warning"
        elif lv == "CRITICAL":
            pri = "crit"

    entries = _journal_query(services, since=since, until=until, grep=grep, priority=pri, lines=limit * 2)

    # Post-filters that journalctl doesn't do natively
    if trace_id:
        entries = [e for e in entries if e.get("trace_id") == trace_id]
    if task_id is not None:
        entries = [e for e in entries if e.get("task_id") == task_id]
    if level:
        wanted = LEVELS[LEVELS.index(level.upper()):] if level.upper() in LEVELS else None
        if wanted:
            entries = [e for e in entries if e.get("level") in wanted]

    entries = entries[-limit:]
    return {
        "logs": entries,
        "count": len(entries),
        "filters": {
            "service": services, "level": level, "since": since, "until": until,
            "grep": grep, "trace_id": trace_id, "task_id": task_id, "limit": limit,
        },
    }


@router.get("/trace/{trace_id}")
async def trace_path(
    trace_id: str,
    since: str | None = Query("24 hours ago"),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """All log entries for a single trace_id across every CFF service.

    Returns events ordered by timestamp so you can see the path:
        api  → scheduler → ingestion → processor → voice → publishing → done
    """
    services = KNOWN_CFF_SERVICES
    entries = _journal_query(services, since=since, grep=trace_id, lines=2000)
    entries = [e for e in entries if e.get("trace_id") == trace_id]

    # Build a per-service summary
    per_service: dict[str, int] = Counter()
    levels: dict[str, int] = Counter()
    for e in entries:
        per_service[e.get("service") or "?"] += 1
        levels[e.get("level") or "INFO"] += 1

    return {
        "trace_id": trace_id,
        "events": entries,
        "count": len(entries),
        "per_service": dict(per_service),
        "by_level": dict(levels),
        "first_seen": entries[0]["timestamp"] if entries else None,
        "last_seen": entries[-1]["timestamp"] if entries else None,
    }


@router.get("/tail/{service}")
async def tail_service(
    service: str,
    lines: int = Query(100, ge=1, le=2000),
    level: str | None = Query(None),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Last N lines of one service. Cheap — no time filter, just `journalctl -n`."""
    pri = None
    if level:
        lv = level.upper()
        if lv == "ERROR":
            pri = "err"
        elif lv == "WARNING":
            pri = "warning"
    entries = _journal_query([service], priority=pri, lines=lines)
    return {"service": service, "logs": entries, "count": len(entries)}


@router.get("/analyze")
async def analyze_logs(
    since: str = Query("1 hour ago"),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Aggregate + anomaly hints over a time window.

    Returns:
      - per_service: counts by level
      - top_errors: most frequent error message stems
      - top_traces: trace_ids with most ERROR entries (likely failed jobs)
      - anomalies: heuristic flags (e.g. service with >10x avg error rate)
      - summary: human-readable summary so an AI can act on it directly
    """
    services = KNOWN_CFF_SERVICES + _list_stream_units()
    entries = _journal_query(services, since=since, lines=5000)

    per_service: dict[str, Counter] = defaultdict(Counter)
    error_msgs: Counter = Counter()
    error_traces: Counter = Counter()

    for e in entries:
        svc = e.get("service") or "?"
        lv = e.get("level") or "INFO"
        per_service[svc][lv] += 1
        if lv in ("ERROR", "CRITICAL"):
            stem = (e.get("message") or "").splitlines()[0][:160]
            error_msgs[stem] += 1
            tid = e.get("trace_id")
            if tid:
                error_traces[tid] += 1

    # Convert Counters → plain dicts for JSON
    per_service_out = {svc: dict(cnts) for svc, cnts in per_service.items()}

    # Anomaly heuristic: a service with > 5 errors AND > 5x the median error count
    error_counts = [cnts.get("ERROR", 0) + cnts.get("CRITICAL", 0) for cnts in per_service.values()]
    median = sorted(error_counts)[len(error_counts) // 2] if error_counts else 0
    anomalies: list[dict[str, Any]] = []
    for svc, cnts in per_service.items():
        errs = cnts.get("ERROR", 0) + cnts.get("CRITICAL", 0)
        if errs > 5 and (median == 0 or errs > 5 * max(median, 1)):
            anomalies.append({"service": svc, "errors": errs, "median_baseline": median,
                              "hint": f"{svc} produced {errs} errors — {errs / max(median, 1):.1f}x baseline"})

    summary_parts: list[str] = []
    total_logs = len(entries)
    total_errors = sum(c.get("ERROR", 0) + c.get("CRITICAL", 0) for c in per_service.values())
    summary_parts.append(f"Window: {since}. Lines: {total_logs}. Errors+critical: {total_errors}.")
    if anomalies:
        summary_parts.append("Anomalies: " + "; ".join(a["hint"] for a in anomalies))
    if error_msgs:
        top = error_msgs.most_common(3)
        summary_parts.append("Top errors: " + " | ".join(f"({n}) {msg}" for msg, n in top))

    return {
        "window_since": since,
        "total_lines": total_logs,
        "total_errors": total_errors,
        "per_service": per_service_out,
        "top_errors": [{"message": m, "count": n} for m, n in error_msgs.most_common(15)],
        "top_failing_traces": [{"trace_id": t, "error_count": n}
                                for t, n in error_traces.most_common(20)],
        "anomalies": anomalies,
        "summary": " ".join(summary_parts),
    }


@router.get("/stats")
async def log_stats(
    since: str = Query("1 hour ago"),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Lightweight per-service counts. Faster than analyze when you only need volumes."""
    services = KNOWN_CFF_SERVICES + _list_stream_units()
    entries = _journal_query(services, since=since, lines=10000)
    per_service: dict[str, Counter] = defaultdict(Counter)
    for e in entries:
        svc = e.get("service") or "?"
        per_service[svc][e.get("level") or "INFO"] += 1
    return {
        "window_since": since,
        "per_service": {svc: dict(cnts) for svc, cnts in per_service.items()},
        "total_lines": len(entries),
    }
