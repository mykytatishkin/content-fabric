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


@router.post("/start")
async def start_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}
    if not s.get("enabled"):
        return {"ok": False, "error": "Stream disabled"}

    code, output = systemd_manager.start(s["service_name"])
    st = systemd_manager.status(s["service_name"])

    # Записать last_start_at
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
        "ts": int(time.time()),
    }


@router.post("/stop")
async def stop_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}

    code, output = systemd_manager.stop(s["service_name"])
    st = systemd_manager.status(s["service_name"])
    return {
        "ok": code == 0,
        "action": "stop",
        "id": id,
        "service": s["service_name"],
        "code": code,
        "output": output,
        "status": st,
        "ts": int(time.time()),
    }


@router.post("/restart")
async def restart_stream(id: int = Form(...), user: dict = Depends(get_current_admin)):
    s = _fetch_stream(id)
    if not s:
        return {"ok": False, "error": "Not found"}

    code, output = systemd_manager.restart(s["service_name"])
    st = systemd_manager.status(s["service_name"])
    return {
        "ok": code == 0,
        "action": "restart",
        "id": id,
        "service": s["service_name"],
        "code": code,
        "output": output,
        "status": st,
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
