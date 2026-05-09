#!/usr/bin/env python3
"""DLE failure monitor — runs every 2h via cron, reports failure rate to Telegram.

Reads recent task outcomes from `content_upload_queue_tasks` and corresponding
worker logs to surface:
  - failure rate over last N hours
  - top error patterns (clustered by message stem)
  - per-source breakdown
  - sample failing task IDs for quick triage

Posts a summary to Telegram if failure_rate >= 50% OR if there are any
recurring 403/404 / FK / NoneType errors. Otherwise stays silent (no spam).

Usage (cron, every 2h):
  0 */2 * * * /opt/content-fabric/prod/venv/bin/python -m scripts.dle_failure_monitor

Env (read from /opt/content-fabric/.env via shared.env):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  CFF_FAILURE_MONITOR_WINDOW_HOURS  (default 2)
  CFF_FAILURE_MONITOR_THRESHOLD_PCT (default 50)
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger("dle_failure_monitor")

WINDOW_HOURS = int(os.environ.get("CFF_FAILURE_MONITOR_WINDOW_HOURS", "2"))
ALERT_THRESHOLD_PCT = int(os.environ.get("CFF_FAILURE_MONITOR_THRESHOLD_PCT", "50"))


def _fetch_recent_tasks() -> list[dict]:
    """Pull tasks finalized in the last WINDOW_HOURS."""
    from sqlalchemy import text
    from shared.db.connection import get_connection

    sql = text("""
        SELECT t.id, t.channel_id, c.name AS channel_name, t.title, t.status,
               t.error_message, t.completed_at, t.scheduled_at,
               JSON_UNQUOTE(JSON_EXTRACT(t.legacy_add_info, '$.dle_source')) AS dle_source
        FROM content_upload_queue_tasks t
        LEFT JOIN platform_channels c ON c.id = t.channel_id
        WHERE COALESCE(t.completed_at, t.updated_at) >= NOW() - INTERVAL :hours HOUR
          AND t.status IN (1, 2)  -- 1=COMPLETED, 2=FAILED
        ORDER BY t.id DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"hours": WINDOW_HOURS}).mappings().fetchall()
    return [dict(r) for r in rows]


_PATTERN_RULES: list[tuple[str, str]] = [
    (r"403 Client Error: Forbidden",       "DLE source returned 403 — site blocks our requests (UA/IP)"),
    (r"404 Client Error: Not Found",       "DLE asset 404 — broken/moved URL"),
    (r"No such file or directory.*\.mp4",  "Stale source_file_path (legacy/dev path) — task unscheduable"),
    (r"FK.*violat|fk_cuqt",                "FK violation — channel_id missing in platform_channels"),
    (r"NoneType.*not.*str|expected str.*NoneType", "NoneType passed to subprocess — payload field missing"),
    (r"invalid_grant|Token has been expired", "OAuth token revoked — needs reauth"),
    (r"Failed to resolve audio source",     "DLE audio resolution failed (cover/HTML scrape blocked)"),
    (r"DLE processor failed to generate video", "Generic DLE pipeline failure"),
]


def _classify_error(msg: str | None) -> str:
    if not msg:
        return "(no error message)"
    msg = str(msg)
    for pattern, label in _PATTERN_RULES:
        if re.search(pattern, msg, re.IGNORECASE):
            return label
    return f"OTHER: {msg[:120]}"


def _build_report(tasks: list[dict]) -> str:
    if not tasks:
        return ""

    total = len(tasks)
    failed = [t for t in tasks if t["status"] == 2]
    completed = [t for t in tasks if t["status"] == 1]
    fail_count = len(failed)
    fail_pct = (fail_count / total * 100.0) if total else 0.0

    by_pattern: Counter = Counter()
    by_source: dict[str, list[int]] = defaultdict(list)
    for t in failed:
        by_pattern[_classify_error(t.get("error_message"))] += 1
        src = t.get("dle_source") or t.get("channel_name") or "?"
        by_source[src].append(t["id"])

    lines: list[str] = []
    emoji = "🟢" if fail_pct < 25 else ("🟡" if fail_pct < ALERT_THRESHOLD_PCT else "🔴")
    lines.append(f"{emoji} CFF DLE failure monitor — last {WINDOW_HOURS}h")
    lines.append(f"Tasks total: {total} (✓ {len(completed)} / ✗ {fail_count}, {fail_pct:.0f}% fail)")

    if fail_count:
        lines.append("")
        lines.append("Top error classes:")
        for label, n in by_pattern.most_common(6):
            lines.append(f"  • {n}× {label}")

        lines.append("")
        lines.append("Per source:")
        for src, ids in sorted(by_source.items(), key=lambda x: -len(x[1]))[:10]:
            sample = ",".join(f"#{i}" for i in ids[:3])
            extra = f" (+{len(ids)-3} more)" if len(ids) > 3 else ""
            lines.append(f"  • {src}: {len(ids)} fail — {sample}{extra}")

    return "\n".join(lines)


def _should_alert(report: str, fail_pct: float, error_classes: int) -> bool:
    if fail_pct >= ALERT_THRESHOLD_PCT:
        return True
    # Even at lower fail rates, if a known-bad pattern repeats, alert.
    return error_classes > 0 and fail_pct >= 25


def main() -> int:
    import shared.env  # loads /opt/content-fabric/.env  # noqa: F401
    from shared.logging_config import setup_logging
    setup_logging(service_name="dle-failure-monitor")

    tasks = _fetch_recent_tasks()
    if not tasks:
        logger.info("Window empty (no tasks finalized in last %dh) — quiet.", WINDOW_HOURS)
        return 0

    failed = [t for t in tasks if t["status"] == 2]
    fail_pct = len(failed) / len(tasks) * 100.0
    report = _build_report(tasks)

    logger.info(report.replace("\n", " | "))

    if _should_alert(report, fail_pct, error_classes=len(set(_classify_error(t.get("error_message")) for t in failed))):
        try:
            from shared.notifications import telegram
            telegram.send(report)
            logger.warning("Alert posted to Telegram (fail_pct=%.0f%%)", fail_pct)
        except Exception:
            logger.exception("Failed to post Telegram alert")
            return 2
    else:
        logger.info("Below alert threshold (%.0f%% < %d%%) — silent.", fail_pct, ALERT_THRESHOLD_PCT)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
