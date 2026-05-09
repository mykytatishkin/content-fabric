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

Every response is JSON. Sources:
  - For cff-* services that systemd writes to /var/log/{service}.log via
    `StandardOutput=append:`, we parse the file directly (this is where the
    Python-formatted lines with [trace=… task=…] annotations live).
  - For stream-* (and as a fallback / for systemd lifecycle events) we use
    `journalctl --output=json` and post-process to extract trace_id / task_id
    from the MESSAGE text.

Auth: admin only (Depends get_current_admin) — these endpoints expose
host-level diagnostic data (journald logs, trace_ids) and must not leak
to non-admin tenants.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_admin

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

# Where systemd writes per-service stdout for cff-* units. Each unit is set up
# (in deploy/systemd/*.service) with `StandardOutput=append:/var/log/{name}.log`,
# so journalctl only contains lifecycle events for these units. We must read
# the file directly to see app-level logs.
LOG_DIR = Path(os.environ.get("CFF_LOG_DIR", "/var/log"))

# Patterns to extract context from log message text
_TRACE_PATTERN = re.compile(r"(?:trace_id|trace)[=: ]([0-9a-fA-F\-]{16,40})")
_TASK_PATTERN = re.compile(r"(?:task_id|task)[=: ](\d+)", re.IGNORECASE)
_LEVEL_PATTERN = re.compile(r"\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\b")

# Format Python's default formatter writes to /var/log/cff-*.log:
#   "2026-05-09 21:21:13 logger.name LEVEL message"
_FILE_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s+"
    r"(?P<logger>\S+)\s+"
    r"(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s+"
    r"(?P<message>.*)$"
)

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
    ts: datetime | None = None
    iso: str | None = None
    if ts_us:
        try:
            ts = datetime.fromtimestamp(int(ts_us) / 1_000_000, tz=timezone.utc)
            iso = ts.isoformat()
        except Exception:
            ts = None
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

    # Prefer the unit we asked journalctl for (UNIT field set by systemd when
    # systemd itself emits the message — e.g. lifecycle events from PID 1).
    # _SYSTEMD_UNIT for those is "init.scope", which is useless to us.
    unit_raw = (
        raw.get("UNIT")
        or raw.get("_SYSTEMD_UNIT", "")
        or raw.get("SYSLOG_IDENTIFIER", "")
        or ""
    )
    if isinstance(unit_raw, list):
        try:
            unit_raw = bytes(unit_raw).decode("utf-8", errors="replace")
        except Exception:
            unit_raw = str(unit_raw)
    unit = str(unit_raw)
    if unit == "init.scope":
        # Fall back: many lifecycle messages have the target unit in the body.
        m_unit = re.search(r"\b([\w.-]+)\.service\b", message[:200])
        if m_unit:
            unit = m_unit.group(0)
    if unit.endswith(".service"):
        unit = unit.removesuffix(".service")

    trace_match = _TRACE_PATTERN.search(message)
    task_match = _TASK_PATTERN.search(message)

    return {
        "timestamp": iso,
        "_dt": ts,  # internal, stripped before returning
        "level": level,
        "service": unit,
        "message": message,
        "trace_id": trace_match.group(1).lower() if trace_match else None,
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


# ─── File-based parser (cff-* services log to /var/log/cff-*.log) ────


def _parse_since(since: str | None) -> datetime | None:
    """Best-effort parse of journalctl-style 'since' strings → UTC datetime.

    Supports:
      - "N min/minutes/hour/hours/day/days ago"
      - ISO timestamps: "2026-05-07 12:00", "2026-05-07T12:00:00"
      - "yesterday", "today"
    Returns None on failure (callers should fall back to scanning everything).
    """
    if not since:
        return None
    s = since.strip().lower()
    now = datetime.now(timezone.utc)
    if s == "now":
        return now
    if s == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if s == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    m = re.match(r"^(\d+)\s+(second|sec|minute|min|hour|hr|day)s?\s+ago$", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith(("second", "sec")):
            return now - timedelta(seconds=n)
        if unit.startswith(("minute", "min")):
            return now - timedelta(minutes=n)
        if unit.startswith(("hour", "hr")):
            return now - timedelta(hours=n)
        if unit.startswith("day"):
            return now - timedelta(days=n)
    # ISO-like — try a few common forms
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(since, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _file_path_for(service: str) -> Path:
    """Resolve /var/log/{service}.log (no traversal — service is checked by caller)."""
    safe = service.replace("/", "").replace("..", "")
    return LOG_DIR / f"{safe}.log"


def _parse_file_line(service: str, raw_line: str) -> dict[str, Any] | None:
    """Parse one line of /var/log/{service}.log into our normalized shape.

    Returns None for lines that don't match the standard formatter (so the
    caller can append them to the previous entry as continuation — typical
    for tracebacks and uvicorn-style ``INFO:     ...`` access lines).
    """
    m = _FILE_LINE_RE.match(raw_line)
    if not m:
        return None
    ts_str = m.group("ts").replace("T", " ").replace(",", ".")
    try:
        # File logger writes server-local time without tz. Treat naive
        # timestamps as UTC so the API contract (always ISO with offset) holds.
        ts = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        iso = ts.isoformat()
    except Exception:
        ts = None
        iso = None

    lv = m.group("level").upper()
    level = "WARNING" if lv == "WARN" else ("CRITICAL" if lv == "FATAL" else lv)
    message = m.group("message")
    trace_match = _TRACE_PATTERN.search(message)
    task_match = _TASK_PATTERN.search(message)
    return {
        "timestamp": iso,
        "_dt": ts,  # internal — stripped before returning to clients
        "level": level,
        "service": service,
        "message": message,
        "logger": m.group("logger"),
        "trace_id": trace_match.group(1).lower() if trace_match else None,
        "task_id": int(task_match.group(1)) if task_match else None,
        "pid": None,
        "host": None,
    }


def _read_log_file(service: str, max_lines: int = 5000) -> list[dict[str, Any]]:
    """Read the tail of /var/log/{service}.log and return parsed entries.

    Continuation lines (no timestamp prefix) are appended to the previous
    entry's `message` so tracebacks stay attached to the ERROR line.
    """
    path = _file_path_for(service)
    if not path.is_file():
        return []
    # Read only the tail to bound memory. ~5x the requested lines covers
    # traceback continuations comfortably.
    read_lines = max(max_lines * 5, 500)
    try:
        # Use `tail -n` — handles huge log files efficiently.
        r = subprocess.run(
            ["tail", "-n", str(read_lines), str(path)],
            capture_output=True, text=True, timeout=10,
        )
        raw = r.stdout
    except Exception:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                raw = fh.read()
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return []

    entries: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line:
            continue
        parsed = _parse_file_line(service, line)
        if parsed is None:
            # Continuation (e.g. traceback). Append to previous entry's message.
            if entries:
                entries[-1]["message"] += "\n" + line
                if not entries[-1].get("trace_id"):
                    tm = _TRACE_PATTERN.search(line)
                    if tm:
                        entries[-1]["trace_id"] = tm.group(1).lower()
            continue
        entries.append(parsed)
    return entries


def _query_logs(
    services: list[str],
    since: str | None = None,
    until: str | None = None,
    grep: str | None = None,
    level: str | None = None,
    lines: int = 200,
) -> list[dict[str, Any]]:
    """Unified multi-source query.

    For each requested service:
      - If /var/log/{service}.log exists → read from file (these are the rich
        application logs with trace_id annotations).
      - Otherwise → fall back to journald.

    Always pulls from journal too for stream-* services and systemd lifecycle
    events. Results are merged, time-sorted, and trimmed to `lines`.
    """
    since_dt = _parse_since(since)
    until_dt = _parse_since(until) if until else None
    wanted_levels: set[str] | None = None
    if level:
        lv = level.upper()
        if lv in LEVELS:
            wanted_levels = set(LEVELS[LEVELS.index(lv):])

    all_entries: list[dict[str, Any]] = []
    journal_only_services: list[str] = []
    for svc in services:
        if _file_path_for(svc).is_file():
            file_entries = _read_log_file(svc, max_lines=max(lines * 3, 600))
            all_entries.extend(file_entries)
        else:
            journal_only_services.append(svc)

    # Pull journal for any service we didn't have a file for, plus lifecycle
    # events for the file-backed ones (it's harmless — the timestamps deduplicate
    # naturally and lifecycle events tell us about restarts).
    pri = None
    if level:
        lv = level.upper()
        if lv == "ERROR":
            pri = "err"
        elif lv == "WARNING":
            pri = "warning"
        elif lv == "CRITICAL":
            pri = "crit"
    journal_target = journal_only_services if journal_only_services else services
    journal_entries = _journal_query(
        journal_target, since=since, until=until, grep=grep,
        priority=pri, lines=max(lines * 2, 200),
    )
    all_entries.extend(journal_entries)

    # Apply post-filters on the merged set.
    def _keep(e: dict[str, Any]) -> bool:
        if wanted_levels and e.get("level") not in wanted_levels:
            return False
        if grep:
            try:
                if not re.search(grep, e.get("message") or "", re.IGNORECASE):
                    return False
            except re.error:
                if grep.lower() not in (e.get("message") or "").lower():
                    return False
        if since_dt and e.get("_dt") and e["_dt"] < since_dt:
            return False
        if until_dt and e.get("_dt") and e["_dt"] > until_dt:
            return False
        return True

    filtered = [e for e in all_entries if _keep(e)]

    # Sort chronologically. Fall back to ISO string compare when no _dt.
    def _sort_key(e: dict[str, Any]) -> str:
        return e.get("timestamp") or ""

    filtered.sort(key=_sort_key)
    filtered = filtered[-lines:]

    # Strip internal-only fields before returning.
    for e in filtered:
        e.pop("_dt", None)
    return filtered


def _looks_like_journalctl_time(s: str) -> bool:
    """Heuristic: journalctl accepts many formats we don't fully model.

    We only emit a 'malformed since' warning when the string clearly does not
    match any plausible journalctl pattern (e.g. random words). This keeps
    'now', 'last hour', 'monday' etc. from triggering false positives.
    """
    s = s.strip().lower()
    if not s:
        return False
    if any(s.startswith(p) for p in ("now", "today", "yesterday", "last", "next", "@")):
        return True
    # Contains a digit? likely a timestamp / "N min ago"
    if re.search(r"\d", s):
        return True
    return False


# ─── Endpoints ───────────────────────────────────────────────────────


@router.get("/services")
async def list_services(user: dict = Depends(get_current_admin)) -> dict[str, Any]:
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
    user: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    """Filtered log query.

    The result is shaped for AI consumption:
        - timestamp ISO 8601 UTC
        - extracted trace_id / task_id when present
        - level normalized to WARNING/ERROR/INFO/DEBUG
        - `warnings` non-empty when input couldn't be honoured (e.g. unparseable since)
    """
    services = service or (KNOWN_CFF_SERVICES + _list_stream_units())

    warnings: list[str] = []
    if since and _parse_since(since) is None and not _looks_like_journalctl_time(since):
        warnings.append(
            f"Could not parse 'since={since}'. Use formats like '10 min ago', "
            f"'2 hours ago', '2026-05-07 12:00', or 'yesterday'."
        )
    if until and _parse_since(until) is None and not _looks_like_journalctl_time(until):
        warnings.append(f"Could not parse 'until={until}'.")

    entries = _query_logs(
        services, since=since, until=until, grep=grep,
        level=level, lines=limit * 2,
    )

    # Post-filters that need the parsed entries
    if trace_id:
        tid = trace_id.lower()
        entries = [e for e in entries if (e.get("trace_id") or "").lower() == tid]
    if task_id is not None:
        entries = [e for e in entries if e.get("task_id") == task_id]

    entries = entries[-limit:]
    return {
        "logs": entries,
        "count": len(entries),
        "filters": {
            "service": services, "level": level, "since": since, "until": until,
            "grep": grep, "trace_id": trace_id, "task_id": task_id, "limit": limit,
        },
        "warnings": warnings,
    }


@router.get("/trace/{trace_id}")
async def trace_path(
    trace_id: str,
    since: str | None = Query("24 hours ago"),
    user: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    """All log entries for a single trace_id across every CFF service.

    Returns events ordered by timestamp so you can see the path:
        api  → scheduler → ingestion → processor → voice → publishing → done
    """
    services = KNOWN_CFF_SERVICES + _list_stream_units()
    entries = _query_logs(services, since=since, grep=trace_id, lines=5000)
    tid = trace_id.lower()
    entries = [e for e in entries if (e.get("trace_id") or "").lower() == tid]

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
    user: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    """Last N lines of one service. Reads /var/log/{service}.log when present,
    else falls back to `journalctl -n`."""
    entries = _query_logs([service], level=level, lines=lines)
    return {"service": service, "logs": entries, "count": len(entries)}


@router.get("/analyze")
async def analyze_logs(
    since: str = Query("1 hour ago"),
    user: dict = Depends(get_current_admin),
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
    entries = _query_logs(services, since=since, lines=5000)

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
    user: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    """Lightweight per-service counts. Faster than analyze when you only need volumes."""
    services = KNOWN_CFF_SERVICES + _list_stream_units()
    entries = _query_logs(services, since=since, lines=10000)
    per_service: dict[str, Counter] = defaultdict(Counter)
    for e in entries:
        svc = e.get("service") or "?"
        per_service[svc][e.get("level") or "INFO"] += 1
    return {
        "window_since": since,
        "per_service": {svc: dict(cnts) for svc, cnts in per_service.items()},
        "total_lines": len(entries),
    }
