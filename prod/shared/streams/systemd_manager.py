"""Тонкая обёртка над systemctl. Заменяет Yii common/services/SystemdService.php.

Возвращает структурированный JSON, совместимый с фронтендом.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from typing import Any

logger = logging.getLogger(__name__)

# Список свойств systemctl show, которые парсим в один вызов
_SHOW_PROPS = [
    "ActiveState",
    "SubState",
    "MainPID",
    "ExecMainStatus",
    "ExecMainStartTimestamp",
    "RuntimeMaxUSec",
]


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    """Выполнить команду, вернуть (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as exc:
        return 127, "", f"command not found: {exc}"


def _parse_show_output(stdout: str) -> dict[str, str]:
    """`systemctl show` возвращает Key=Value по строкам."""
    result: dict[str, str] = {}
    for line in stdout.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _parse_runtime_max_usec(value: str) -> int:
    """RuntimeMaxUSec может быть числом или 'infinity'. Возвращает секунды (0 если бесконечно)."""
    if not value or value in ("infinity", "0"):
        return 0
    try:
        return int(value) // 1_000_000
    except ValueError:
        return 0


def _parse_start_timestamp(value: str) -> int | None:
    """ExecMainStartTimestamp выглядит как 'Sat 2026-05-02 14:30:21 UTC'.
    Возвращает unix timestamp или None."""
    if not value or value in ("0", "n/a"):
        return None
    # Удалить день недели если есть
    cleaned = re.sub(r"^[A-Za-z]+\s+", "", value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"):
        try:
            t = time.strptime(cleaned, fmt)
            return int(time.mktime(t))
        except ValueError:
            continue
    return None


def status(unit: str) -> dict[str, Any]:
    """Получить статус сервиса (совместимо с Yii actionStatus результатом)."""
    cmd = ["systemctl", "show", unit, "--property=" + ",".join(_SHOW_PROPS), "--no-pager"]
    code, stdout, stderr = _run(cmd, timeout=5)
    if code == 127:
        return {"unit": unit, "active": False, "activeState": "sudo_required",
                "subState": "", "pid": 0, "exitCode": 0,
                "since_ts": None, "runtime_max_sec": 0,
                "elapsed_sec": None, "remaining_sec": None, "end_ts": None}
    if code != 0:
        return {"unit": unit, "active": False, "activeState": "error",
                "subState": stderr.strip()[:80], "pid": 0, "exitCode": code,
                "since_ts": None, "runtime_max_sec": 0,
                "elapsed_sec": None, "remaining_sec": None, "end_ts": None}

    props = _parse_show_output(stdout)
    active_state = props.get("ActiveState", "unknown")
    sub_state = props.get("SubState", "")
    pid = int(props.get("MainPID", 0) or 0)
    exit_code = int(props.get("ExecMainStatus", 0) or 0)
    since_ts = _parse_start_timestamp(props.get("ExecMainStartTimestamp", ""))
    runtime_max = _parse_runtime_max_usec(props.get("RuntimeMaxUSec", ""))

    elapsed: int | None = None
    remaining: int | None = None
    end_ts: int | None = None
    if since_ts:
        elapsed = max(0, int(time.time()) - since_ts)
        if runtime_max > 0:
            end_ts = since_ts + runtime_max
            remaining = max(0, end_ts - int(time.time()))

    return {
        "unit": unit,
        "active": (active_state == "active" and sub_state == "running"),
        "activeState": active_state,
        "subState": sub_state,
        "pid": pid,
        "exitCode": exit_code,
        "since_ts": since_ts,
        "runtime_max_sec": runtime_max,
        "elapsed_sec": elapsed,
        "remaining_sec": remaining,
        "end_ts": end_ts,
    }


def _do_action(action: str, unit: str) -> tuple[int, str]:
    code, stdout, stderr = _run(["systemctl", action, unit], timeout=30)
    output = (stdout + stderr).strip()
    return code, output


def start(unit: str) -> tuple[int, str]:
    return _do_action("start", unit)


def stop(unit: str) -> tuple[int, str]:
    return _do_action("stop", unit)


def restart(unit: str) -> tuple[int, str]:
    return _do_action("restart", unit)


def tail(unit: str, lines: int = 40) -> str:
    """Последние N строк journalctl для unit."""
    code, stdout, stderr = _run(
        ["journalctl", "-u", unit, "-n", str(int(lines)), "--no-pager", "--output=short-iso"],
        timeout=15,
    )
    return stdout if code == 0 else (stderr or "(no logs)")


def daemon_reload() -> tuple[int, str]:
    return _do_action("daemon-reload", "")


def reset_failed(unit: str) -> tuple[int, str]:
    return _do_action("reset-failed", unit)
