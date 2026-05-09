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
import posixpath
import re
import time

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import get_current_admin
from app.core.config import settings
from shared.db.connection import get_connection
from shared.streams import lifecycle, provisioner, systemd_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# ─── Schemas ─────────────────────────────────────────────────────────


class StreamCreateRequest(BaseModel):
    name: str
    # ``service_name`` and ``workdir`` are auto-derived from ``name`` when
    # omitted — Yii beforeValidate parity (StreamConfiguration::beforeValidate
    # in the legacy frontend).  See ``_derive_service_name`` /
    # ``_derive_workdir`` below.
    service_name: str | None = None
    workdir: str | None = None
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


# ─── Yii-parity defaults ─────────────────────────────────────────────


_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _derive_service_name(name: str) -> str:
    """Yii parity: ``stream-<name>.service`` (matches existing rows)."""
    return f"stream-{name}.service"


def _derive_workdir(name: str) -> str:
    """Yii parity: ``<STREAMS_ROOT>/<name>`` (always POSIX paths — server
    runs on Linux even when this code is unit-tested on Windows)."""
    root = (settings.STREAMS_ROOT or "").rstrip("/") or "/var/lib/cff/streams"
    return posixpath.join(root, name)


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


@router.post("/start")
async def start_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}
    if not s.get("enabled"):
        return {"ok": False, "error": "Stream disabled"}

    res = lifecycle.start_stream(s)
    st = systemd_manager.status(s["service_name"])

    if res.get("ok"):
        try:
            with get_connection() as conn:
                conn.execute(text(
                    "UPDATE live_stream_configurations SET updated_at = NOW() WHERE id = :id"
                ), {"id": id})
        except Exception:
            logger.exception("Failed to update updated_at for stream %s", id)

    return {
        "ok": res["ok"],
        "id": id,
        "service": s["service_name"],
        "code": res["code"],
        "output": res["output"],
        "status": st,
        "youtube_broadcast_id": res.get("youtube_broadcast_id"),
        "youtube_stream_id": res.get("youtube_stream_id"),
        "youtube_prep_error": res.get("youtube_prep_error"),
        "youtube_live_error": res.get("youtube_live_error"),
        "ts": int(time.time()),
    }


@router.post("/stop")
async def stop_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}

    res = lifecycle.stop_stream(s)
    st = systemd_manager.status(s["service_name"])
    return {
        "ok": res["ok"],
        "action": "stop",
        "id": id,
        "service": s["service_name"],
        "code": res["code"],
        "output": res["output"],
        "status": st,
        "youtube_broadcast_id": res.get("youtube_broadcast_id"),
        "youtube_complete_error": res.get("youtube_complete_error"),
        "ts": int(time.time()),
    }


@router.post("/restart")
async def restart_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}

    # Reuse stop → start so the YouTube broadcast lifecycle (complete → ensure
    # → live) is exercised end-to-end. Plain `systemctl restart` would only
    # bounce ffmpeg and leave the broadcast in whatever stale state it was in.
    stop_res = lifecycle.stop_stream(s)
    s = _fetch_stream(id) or s
    start_res = lifecycle.start_stream(s)

    st = systemd_manager.status(s["service_name"])
    return {
        "ok": start_res["ok"],
        "action": "restart",
        "id": id,
        "service": s["service_name"],
        "code": start_res["code"],
        "output": (stop_res.get("output") or "") + "\n" + (start_res.get("output") or ""),
        "status": st,
        "youtube_broadcast_id": start_res.get("youtube_broadcast_id"),
        "youtube_stream_id": start_res.get("youtube_stream_id"),
        "youtube_complete_error": stop_res.get("youtube_complete_error"),
        "youtube_prep_error": start_res.get("youtube_prep_error"),
        "youtube_live_error": start_res.get("youtube_live_error"),
        "ts": int(time.time()),
    }


@router.post("/reconcile")
async def reconcile_one(id: int = Form(...), user: dict = Depends(get_current_admin)):
    """Heal a single stream: if its systemd unit isn't healthy, run full lifecycle.

    Same code-path as the periodic scheduler reconciler — exposed for manual
    triage via the dashboard's "Heal" button.
    """
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}
    if not s.get("enabled"):
        return {"ok": False, "error": "Stream disabled"}
    return {"ok": True, "result": lifecycle.reconcile(s), "ts": int(time.time())}


@router.post("/reconcile-all")
async def reconcile_all(user: dict = Depends(get_current_admin)):
    """Run reconcile() across every enabled stream — manual trigger of the loop."""
    rows = _fetch_streams(only_enabled=True)
    results = [{"id": s["id"], **lifecycle.reconcile(s)} for s in rows]
    return {"ok": True, "results": results, "ts": int(time.time())}


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
    """Создать новый стрим + сразу провижионинг (env, runner, systemd unit).

    Yii beforeValidate parity — ``service_name`` and ``workdir`` are
    auto-derived from ``name`` if not supplied.
    """
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")
    if not _NAME_RE.match(name):
        raise HTTPException(
            status_code=422,
            detail="name must contain only [A-Za-z0-9_-]",
        )
    if not (body.stream_key or "").strip():
        raise HTTPException(status_code=422, detail="stream_key is required")

    payload = body.model_dump()
    payload["name"] = name
    if not (payload.get("service_name") or "").strip():
        payload["service_name"] = _derive_service_name(name)
    if not (payload.get("workdir") or "").strip():
        payload["workdir"] = _derive_workdir(name)

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
        result = conn.execute(sql, payload)
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
