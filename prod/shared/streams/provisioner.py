"""Создаёт/синхронизирует systemd unit + env + runner для одного стрима.

Замена Yii common/services/StreamProvisionerService.php + console/controllers/YtController.

Все артефакты на диске:
  /etc/systemd/system/stream-<service_name>.service
  /etc/aiyoutube/streams/<name>.env
  <workdir>/yt_stream_runner.sh        (если runner_path пуст)
  <workdir>/videos/playlist.txt        (создаётся пустой если нет)
"""

from __future__ import annotations

import logging
import os
from typing import Any

from shared.streams import systemd_manager
from shared.streams.runner_template import (
    YT_STREAM_RUNNER,
    render_env_file,
    render_systemd_unit,
)

logger = logging.getLogger(__name__)

ETC_STREAMS_DIR = "/etc/aiyoutube/streams"
SYSTEMD_DIR = "/etc/systemd/system"


def _write_file(path: str, content: str, mode: int = 0o644) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(path, mode)


def _ensure_dir(path: str, mode: int = 0o775) -> None:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    os.chmod(path, mode)


def _normalize_rtmp_host(rtmp_base: str | None, rtmp_host: str | None) -> str:
    if rtmp_host:
        return rtmp_host.strip()
    if rtmp_base:
        # rtmp://a.rtmp.youtube.com/live2/  → a.rtmp.youtube.com
        h = rtmp_base.replace("rtmp://", "").replace("rtmps://", "")
        h = h.split("/", 1)[0]
        return h
    return "a.rtmp.youtube.com"


def provision_stream(stream: dict[str, Any], reload_systemd: bool = True) -> dict[str, Any]:
    """Создать/обновить артефакты для одного стрима из БД (live_stream_configurations).

    Ожидаемые поля в `stream`:
        id, name, service_name, workdir, stream_key, duration_sec,
        rtmp_base, rtmp_host
    Возвращает dict с путями созданных файлов и результатом daemon-reload.
    """
    sid = stream.get("id")
    name = (stream.get("name") or "").strip()
    service_name = (stream.get("service_name") or "").strip()
    workdir = (stream.get("workdir") or "").strip()
    stream_key = (stream.get("stream_key") or "").strip()
    duration = int(stream.get("duration_sec") or 42900)

    if not name or not service_name or not workdir:
        raise ValueError(f"Stream #{sid}: missing required fields name/service_name/workdir")
    if not stream_key:
        raise ValueError(f"Stream #{sid}: empty stream_key")

    rtmp_host = _normalize_rtmp_host(stream.get("rtmp_base"), stream.get("rtmp_host"))

    # 1. Подготовить workdir и videos/playlist.txt
    videos_dir = os.path.join(workdir, "videos")
    _ensure_dir(workdir)
    _ensure_dir(videos_dir)
    playlist = os.path.join(videos_dir, "playlist.txt")
    if not os.path.isfile(playlist):
        with open(playlist, "w", encoding="utf-8") as f:
            f.write("")
        os.chmod(playlist, 0o664)

    # 2. Runner-скрипт
    runner_path = os.path.join(workdir, "yt_stream_runner.sh")
    _write_file(runner_path, YT_STREAM_RUNNER, mode=0o755)

    # 3. Env-файл /etc/aiyoutube/streams/<name>.env
    env_path = os.path.join(ETC_STREAMS_DIR, f"{name}.env")
    env_content = render_env_file(
        stream_name=name,
        stream_key=stream_key,
        input_dir=videos_dir,
        rtmp_host=rtmp_host,
        runtime_max=duration,
    )
    _write_file(env_path, env_content, mode=0o600)

    # 4. Systemd unit
    unit_full_name = service_name if service_name.endswith(".service") else f"{service_name}.service"
    unit_path = os.path.join(SYSTEMD_DIR, unit_full_name)
    unit_content = render_systemd_unit(
        stream_name=name,
        service_name=service_name,
        workdir=workdir,
        env_file=env_path,
        runner_path=runner_path,
    )
    _write_file(unit_path, unit_content, mode=0o644)

    # 5. daemon-reload
    reload_result = None
    if reload_systemd:
        code, out = systemd_manager.daemon_reload()
        reload_result = {"code": code, "output": out}
        # reset-failed на случай если сервис был в failed
        systemd_manager.reset_failed(unit_full_name)

    logger.info("Provisioned stream #%s '%s' → %s", sid, name, unit_full_name)
    return {
        "ok": True,
        "stream_id": sid,
        "service": unit_full_name,
        "unit_path": unit_path,
        "env_path": env_path,
        "runner_path": runner_path,
        "workdir": workdir,
        "videos_dir": videos_dir,
        "daemon_reload": reload_result,
    }


def provision_all(streams: list[dict[str, Any]]) -> dict[str, Any]:
    """Synchronize all streams. daemon-reload вызывается ОДИН раз в конце."""
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for s in streams:
        try:
            results.append(provision_stream(s, reload_systemd=False))
        except Exception as exc:
            logger.exception("Provision failed for stream #%s", s.get("id"))
            failures.append({"stream_id": s.get("id"), "error": str(exc)})

    code, out = systemd_manager.daemon_reload()
    return {
        "ok": not failures,
        "synced": len(results),
        "failed": len(failures),
        "failures": failures,
        "results": results,
        "daemon_reload": {"code": code, "output": out},
    }
