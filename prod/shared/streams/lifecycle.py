"""Stream lifecycle orchestration — YouTube broadcast prep + systemd + transition.

Single source of truth shared by:
  * `app/api/endpoints/streams.py` — UI-driven `/start`, `/stop`, `/restart`
  * `workers/stream_worker.py`     — RQ-driven reconcile/start/stop jobs
  * `scheduler/jobs.py`            — periodic `reconcile_streams()` health loop

The PHP equivalent (Yii) tied broadcast prep + systemctl ffmpeg in one shot.
Our split: prep first (no ffmpeg yet), systemd start, brief settle delay, then
transition broadcast → ``live``. Mirrors `Yii YoutubeService::goLive` semantics.

Why a separate module: the systemd unit's ``Restart=on-failure`` will re-bounce
ffmpeg on its own, but it does NOT re-prep the YouTube broadcast — so a broadcast
that has gone stale (e.g. CDN ingest dropped, broadcast moved to ``complete``)
keeps yielding RTMP "Input/output error" until something runs the lifecycle
again. The scheduler's reconcile loop is that something.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_connection
from shared.streams import systemd_manager

logger = logging.getLogger(__name__)

# How long to wait after starting the systemd ffmpeg unit before transitioning
# the YouTube broadcast to ``live``. Mirrors the implicit delay the Yii code
# relied on (broadcast won't transition until ingest is "active").
_GO_LIVE_DELAY_SEC = 8


# ── persistence ─────────────────────────────────────────────────────


def persist_broadcast_ids(
    stream_id: int,
    broadcast_id: str | None,
    platform_stream_id: str | None,
) -> None:
    """Persist YouTube broadcast/stream identifiers back to the row."""
    if not broadcast_id and not platform_stream_id:
        return
    try:
        with get_connection() as conn:
            conn.execute(
                text(
                    """
                    UPDATE live_stream_configurations
                    SET platform_broadcast_id = COALESCE(:bid, platform_broadcast_id),
                        platform_stream_id    = COALESCE(:sid, platform_stream_id),
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {"id": stream_id, "bid": broadcast_id, "sid": platform_stream_id},
            )
    except Exception:
        logger.exception("Failed to persist broadcast ids for stream %s", stream_id)


# ── YouTube prep / live / complete ──────────────────────────────────


def prepare_broadcast(s: dict) -> dict:
    """Pre-start YouTube prep: ensure broadcast, bind ingest, push meta.

    Returns ``{"ok": bool, "broadcast_id": str|None, "stream_id": str|None,
    "error": str|None}``. Failures are logged but never raise — callers still
    want the systemd unit to start.
    """
    if not s.get("streaming_account_id"):
        return {"ok": True, "broadcast_id": None, "stream_id": None, "error": None}
    try:
        from shared.youtube.broadcasts import prepare_broadcast_for_start
        from shared.youtube.streaming_accounts import (
            build_service_for_streaming_account,
        )

        service, _ = build_service_for_streaming_account(int(s["streaming_account_id"]))
        prep = prepare_broadcast_for_start(service, s)
        return {
            "ok": True,
            "broadcast_id": prep.get("broadcast_id"),
            "stream_id": prep.get("stream_id"),
            "error": None,
        }
    except Exception as exc:
        logger.exception(
            "YouTube broadcast prep failed for stream %s; starting systemd anyway",
            s.get("id"),
        )
        return {"ok": False, "broadcast_id": None, "stream_id": None, "error": str(exc)}


def go_live(s: dict, broadcast_id: str) -> dict:
    """Transition broadcast to ``live`` after ffmpeg is pushing. Tolerant to errors."""
    try:
        from shared.youtube.broadcasts import transition_broadcast
        from shared.youtube.streaming_accounts import (
            build_service_for_streaming_account,
        )

        service, _ = build_service_for_streaming_account(int(s["streaming_account_id"]))
        transition_broadcast(service, broadcast_id, "live")
        return {"ok": True, "error": None}
    except Exception as exc:
        logger.exception(
            "transition_broadcast(live) failed for stream %s broadcast %s",
            s.get("id"), broadcast_id,
        )
        return {"ok": False, "error": str(exc)}


def complete_broadcast(s: dict) -> dict:
    """Transition broadcast to ``complete`` on stop. Tolerant to errors."""
    bid = (s.get("platform_broadcast_id") or "").strip()
    if not bid or not s.get("streaming_account_id"):
        return {"ok": True, "broadcast_id": None, "error": None}
    try:
        from shared.youtube.broadcasts import transition_broadcast
        from shared.youtube.streaming_accounts import (
            build_service_for_streaming_account,
        )

        service, _ = build_service_for_streaming_account(int(s["streaming_account_id"]))
        transition_broadcast(service, bid, "complete")
        return {"ok": True, "broadcast_id": bid, "error": None}
    except Exception as exc:
        logger.exception(
            "transition_broadcast(complete) failed for stream %s broadcast %s",
            s.get("id"), bid,
        )
        return {"ok": False, "broadcast_id": bid, "error": str(exc)}


# ── high-level orchestration ───────────────────────────────────────


def start_stream(s: dict) -> dict:
    """Full start: prep broadcast → systemd start → wait → transition live."""
    yt_prep = prepare_broadcast(s)
    if yt_prep.get("broadcast_id") or yt_prep.get("stream_id"):
        persist_broadcast_ids(
            int(s["id"]), yt_prep.get("broadcast_id"), yt_prep.get("stream_id")
        )

    code, output = systemd_manager.start(s["service_name"])

    yt_live: dict = {"ok": True, "error": None}
    if code == 0 and yt_prep.get("broadcast_id"):
        time.sleep(_GO_LIVE_DELAY_SEC)
        yt_live = go_live(s, yt_prep["broadcast_id"])

    return {
        "ok": code == 0,
        "code": code,
        "output": output,
        "youtube_broadcast_id": yt_prep.get("broadcast_id"),
        "youtube_stream_id": yt_prep.get("stream_id"),
        "youtube_prep_error": yt_prep.get("error"),
        "youtube_live_error": yt_live.get("error"),
    }


def stop_stream(s: dict) -> dict:
    """Full stop: systemd stop → transition broadcast complete (best-effort)."""
    code, output = systemd_manager.stop(s["service_name"])
    yt = complete_broadcast(s)
    return {
        "ok": code == 0,
        "code": code,
        "output": output,
        "youtube_broadcast_id": yt.get("broadcast_id"),
        "youtube_complete_error": yt.get("error"),
    }


def reconcile(s: dict) -> dict:
    """Heal a stream that systemd alone can't bring back to live.

    Decision tree:
        - systemd unit `active running` AND broadcast_id present → no-op (healthy).
        - otherwise: reset-failed, full `start_stream` (prep + start + go-live).

    Returns a short report dict the caller can log and surface in dashboards.
    """
    unit = s["service_name"]
    st = systemd_manager.status(unit)
    active_state = (st.get("active_state") or "").lower()
    sub_state = (st.get("sub_state") or "").lower()
    is_running = active_state == "active" and sub_state == "running"

    has_broadcast = bool((s.get("platform_broadcast_id") or "").strip())
    if is_running and has_broadcast:
        return {"action": "noop", "reason": "active_running_with_broadcast",
                "ok": True, "stream_id": s.get("id")}

    # Reset systemd's restart-burst counter so a stuck unit can re-enter normal scheduling.
    systemd_manager.reset_failed(unit)

    # If currently active but missing broadcast, stop first to avoid two ffmpeg
    # processes contending. (systemd_manager.stop is idempotent on inactive units.)
    if is_running:
        systemd_manager.stop(unit)

    result = start_stream(s)
    return {
        "action": "started",
        "reason": f"was {active_state}/{sub_state}",
        "ok": result["ok"],
        "stream_id": s.get("id"),
        "broadcast_id": result.get("youtube_broadcast_id"),
        "prep_error": result.get("youtube_prep_error"),
        "live_error": result.get("youtube_live_error"),
        "systemd_code": result.get("code"),
    }
