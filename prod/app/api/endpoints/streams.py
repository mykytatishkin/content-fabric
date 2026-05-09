"""Streams API — replaces Yii frontend/controllers/StreamController.php endpoints.

URLs (compatible with Yii UI):
    GET  /api/v1/streams/status       → { ok, data: [...streams], ts }
    GET  /api/v1/streams/tail?id=N&lines=40
    POST /api/v1/streams/start        body: id=N
    POST /api/v1/streams/stop
    POST /api/v1/streams/restart
    POST /api/v1/streams/sync         body: id=N (re-provision systemd unit)
    POST /api/v1/streams/sync-all     (re-provision all enabled)
    POST /api/v1/streams/             create new stream (Yii actionCreate equivalent)
    GET  /api/v1/streams/             list all streams
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import get_current_admin
from shared.db.connection import get_connection
from shared.streams import provisioner, systemd_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# How long to wait after starting the systemd ffmpeg unit before transitioning
# the YouTube broadcast to ``live``.  Mirrors the implicit delay the legacy Yii
# code relied on (broadcast won't transition until ingest is "active").
_GO_LIVE_DELAY_SEC = 8


# ─── Schemas ─────────────────────────────────────────────────────────


class StreamCreateRequest(BaseModel):
    name: str
    service_name: str
    workdir: str
    stream_key: str
    duration_sec: int = 42900
    rtmp_base: str | None = "rtmp://a.rtmp.youtube.com/live2/"
    rtmp_host: str | None = "a.rtmp.youtube.com"
    streaming_account_id: int | None = None
    channel_id: int | None = None
    title: str | None = None
    description: str | None = None
    tags: str | None = None
    thumbnail_path: str | None = None
    notes: str | None = None


# ─── Helpers ─────────────────────────────────────────────────────────


def _fetch_streams(only_enabled: bool = True) -> list[dict]:
    sql = """
        SELECT id, name, service_name, workdir, stream_key, duration_sec,
               rtmp_host, rtmp_base, channel_id, streaming_account_id,
               platform_broadcast_id, platform_stream_id,
               title, enabled
        FROM live_stream_configurations
        {where}
        ORDER BY id ASC
    """
    where = "WHERE enabled = 1" if only_enabled else ""
    with get_connection() as conn:
        rows = conn.execute(text(sql.format(where=where))).mappings().all()
    return [dict(r) for r in rows]


def _fetch_stream(stream_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(text("""
            SELECT id, name, service_name, workdir, stream_key, duration_sec,
                   rtmp_host, rtmp_base, channel_id, streaming_account_id,
                   platform_broadcast_id, platform_stream_id,
                   title, description, tags, thumbnail_path, enabled
            FROM live_stream_configurations
            WHERE id = :id
        """), {"id": stream_id}).mappings().first()
    return dict(row) if row else None


# ─── Endpoints ───────────────────────────────────────────────────────


@router.get("/status")
async def status_all(user: dict = Depends(get_current_admin)):
    """Список всех enabled стримов + текущий systemctl status каждого."""
    rows = _fetch_streams(only_enabled=True)
    data = []
    for s in rows:
        st = systemd_manager.status(s["service_name"])
        data.append({
            "id": s["id"],
            "yid": s.get("streaming_account_id"),
            "name": s["name"],
            "channel": s.get("channel_id"),
            "service": s["service_name"],
            "stream_key": s.get("stream_key") or "",
            "workdir": s["workdir"],
            "runner_path": "yt_stream_runner.sh",
            "status": st,
        })
    return {"ok": True, "data": data, "ts": int(time.time())}


@router.get("/tail")
async def tail_log(
    id: int = Query(..., gt=0),
    lines: int = Query(40, ge=1, le=1000),
    user: dict = Depends(get_current_admin),
):
    s = _fetch_stream(id)
    if not s:
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"ok": True, "log": systemd_manager.tail(s["service_name"], lines)}


def _persist_broadcast_ids(
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
        logger.exception(
            "Failed to persist broadcast ids for stream %s", stream_id
        )


def _start_youtube_broadcast(s: dict) -> dict:
    """Pre-start YouTube prep: ensure broadcast, bind ingest, push meta.

    Returns ``{"ok": bool, "broadcast_id": str|None, "stream_id": str|None,
    "error": str|None}``.  Failures are logged but never raise — callers still
    want the systemd unit to start.
    """
    if not s.get("streaming_account_id"):
        return {"ok": True, "broadcast_id": None, "stream_id": None, "error": None}

    try:
        from shared.youtube.broadcasts import prepare_broadcast_for_start
        from shared.youtube.streaming_accounts import (
            build_service_for_streaming_account,
        )

        service, _account = build_service_for_streaming_account(
            int(s["streaming_account_id"])
        )
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


def _go_live(s: dict, broadcast_id: str) -> dict:
    """Transition broadcast to ``live`` after ffmpeg is pushing.  Tolerant to errors."""
    try:
        from shared.youtube.broadcasts import transition_broadcast
        from shared.youtube.streaming_accounts import (
            build_service_for_streaming_account,
        )

        service, _ = build_service_for_streaming_account(
            int(s["streaming_account_id"])
        )
        transition_broadcast(service, broadcast_id, "live")
        return {"ok": True, "error": None}
    except Exception as exc:
        logger.exception(
            "transition_broadcast(live) failed for stream %s broadcast %s",
            s.get("id"), broadcast_id,
        )
        return {"ok": False, "error": str(exc)}


def _complete_broadcast(s: dict) -> dict:
    """Transition broadcast to ``complete`` on stop.  Tolerant to errors."""
    bid = (s.get("platform_broadcast_id") or "").strip()
    if not bid or not s.get("streaming_account_id"):
        return {"ok": True, "broadcast_id": None, "error": None}
    try:
        from shared.youtube.broadcasts import transition_broadcast
        from shared.youtube.streaming_accounts import (
            build_service_for_streaming_account,
        )

        service, _ = build_service_for_streaming_account(
            int(s["streaming_account_id"])
        )
        transition_broadcast(service, bid, "complete")
        return {"ok": True, "broadcast_id": bid, "error": None}
    except Exception as exc:
        logger.exception(
            "transition_broadcast(complete) failed for stream %s broadcast %s",
            s.get("id"), bid,
        )
        return {"ok": False, "broadcast_id": bid, "error": str(exc)}


@router.post("/start")
async def start_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}
    if not s.get("enabled"):
        return {"ok": False, "error": "Stream disabled"}

    # 1) YouTube prep (ensure broadcast / bind / meta / thumb) — BEFORE systemd.
    yt_prep = _start_youtube_broadcast(s)
    if yt_prep.get("broadcast_id") or yt_prep.get("stream_id"):
        _persist_broadcast_ids(
            id, yt_prep.get("broadcast_id"), yt_prep.get("stream_id")
        )

    # 2) systemd start (ffmpeg → RTMP).
    code, output = systemd_manager.start(s["service_name"])

    # 3) Wait for ingest to come up, then transition broadcast → live.
    yt_live: dict = {"ok": True, "error": None}
    if code == 0 and yt_prep.get("broadcast_id"):
        time.sleep(_GO_LIVE_DELAY_SEC)
        yt_live = _go_live(s, yt_prep["broadcast_id"])

    st = systemd_manager.status(s["service_name"])

    if code == 0:
        try:
            with get_connection() as conn:
                conn.execute(text("""
                    UPDATE live_stream_configurations
                    SET updated_at = NOW()
                    WHERE id = :id
                """), {"id": id})
        except Exception:
            logger.exception("Failed to update updated_at for stream %s", id)

    return {
        "ok": code == 0,
        "id": id,
        "service": s["service_name"],
        "code": code,
        "output": output,
        "status": st,
        "youtube_broadcast_id": yt_prep.get("broadcast_id"),
        "youtube_stream_id": yt_prep.get("stream_id"),
        "youtube_prep_error": yt_prep.get("error"),
        "youtube_live_error": yt_live.get("error"),
        "ts": int(time.time()),
    }


@router.post("/stop")
async def stop_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}

    # 1) systemd stop first — even if YouTube transition later fails, ffmpeg is gone.
    code, output = systemd_manager.stop(s["service_name"])

    # 2) Transition YouTube broadcast → complete (best-effort).
    yt = _complete_broadcast(s)

    st = systemd_manager.status(s["service_name"])
    return {
        "ok": code == 0,
        "action": "stop",
        "id": id,
        "service": s["service_name"],
        "code": code,
        "output": output,
        "status": st,
        "youtube_broadcast_id": yt.get("broadcast_id"),
        "youtube_complete_error": yt.get("error"),
        "ts": int(time.time()),
    }


@router.post("/restart")
async def restart_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}

    # Reuse stop → start so the YouTube broadcast lifecycle (complete → ensure
    # → live) is exercised end-to-end.  Plain `systemctl restart` would only
    # bounce ffmpeg and leave the broadcast in whatever stale state it was in.
    yt_complete = _complete_broadcast(s)
    code_stop, out_stop = systemd_manager.stop(s["service_name"])

    # re-fetch in case complete cleared platform_broadcast_id (it doesn't
    # today, but keeps this safe if behaviour changes).
    s = _fetch_stream(id) or s
    yt_prep = _start_youtube_broadcast(s)
    if yt_prep.get("broadcast_id") or yt_prep.get("stream_id"):
        _persist_broadcast_ids(
            id, yt_prep.get("broadcast_id"), yt_prep.get("stream_id")
        )
    code_start, out_start = systemd_manager.start(s["service_name"])

    yt_live: dict = {"ok": True, "error": None}
    if code_start == 0 and yt_prep.get("broadcast_id"):
        time.sleep(_GO_LIVE_DELAY_SEC)
        yt_live = _go_live(s, yt_prep["broadcast_id"])

    st = systemd_manager.status(s["service_name"])
    code = code_start
    output = (out_stop or "") + "\n" + (out_start or "")
    return {
        "ok": code == 0,
        "action": "restart",
        "id": id,
        "service": s["service_name"],
        "code": code,
        "output": output,
        "status": st,
        "youtube_broadcast_id": yt_prep.get("broadcast_id"),
        "youtube_stream_id": yt_prep.get("stream_id"),
        "youtube_complete_error": yt_complete.get("error"),
        "youtube_prep_error": yt_prep.get("error"),
        "youtube_live_error": yt_live.get("error"),
        "ts": int(time.time()),
    }


@router.post("/sync")
async def sync_one(id: int = Form(...), user: dict = Depends(get_current_admin)):
    """Re-provision систему файлов одного стрима (env, runner, systemd unit)."""
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}
    try:
        result = provisioner.provision_stream(s, reload_systemd=True)
        return {"ok": True, "output": "synced", "result": result}
    except Exception as exc:
        logger.exception("Sync failed for stream %s", id)
        return {"ok": False, "error": str(exc)}


@router.post("/sync-all")
async def sync_all(user: dict = Depends(get_current_admin)):
    """Re-provision ВСЕХ enabled стримов. Daemon-reload в конце."""
    streams = _fetch_streams(only_enabled=True)
    result = provisioner.provision_all(streams)
    return result


@router.get("/")
async def list_streams(user: dict = Depends(get_current_admin)):
    return {"streams": _fetch_streams(only_enabled=False)}


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_stream(body: StreamCreateRequest, user: dict = Depends(get_current_admin)):
    """Создать новый стрим + сразу провижионинг (env, runner, systemd unit)."""
    sql = text("""
        INSERT INTO live_stream_configurations
            (project_id, streaming_account_id, channel_id, name, service_name, workdir,
             rtmp_host, rtmp_base, stream_key, duration_sec,
             title, description, tags, thumbnail_path, enabled, notes,
             created_at, updated_at)
        VALUES
            (1, :streaming_account_id, :channel_id, :name, :service_name, :workdir,
             :rtmp_host, :rtmp_base, :stream_key, :duration_sec,
             :title, :description, :tags, :thumbnail_path, 1, :notes,
             NOW(), NOW())
    """)
    with get_connection() as conn:
        result = conn.execute(sql, body.model_dump())
        new_id = result.lastrowid
        conn.commit()

    s = _fetch_stream(new_id)
    if not s:
        raise HTTPException(status_code=500, detail="Failed to fetch newly created stream")
    try:
        provision = provisioner.provision_stream(s, reload_systemd=True)
    except Exception as exc:
        logger.exception("Provisioning failed for new stream %s", new_id)
        return {"ok": False, "id": new_id, "error": str(exc)}

    return {"ok": True, "id": new_id, "stream": s, "provision": provision}
