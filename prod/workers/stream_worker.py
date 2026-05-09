"""Stream control worker — RQ job handler for systemd actions + lifecycle.

Actions:
  - start / stop / restart : plain systemctl (legacy compat with Yii UI buttons)
  - reconcile              : full lifecycle heal — broadcast prep, systemd start,
                             go-live transition. Same code path as scheduler's
                             periodic `reconcile_streams()` loop.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_connection
from shared.metrics import instrument_job
from shared.notifications import telegram
from shared.queue.types import StreamControlPayload
from shared.streams import lifecycle
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


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


@instrument_job("stream-control")
def run_stream_control_job(payload: StreamControlPayload) -> dict[str, Any]:
    """Job handler called by rq.

    Recognised `payload.action` values:
        - "start" | "stop" | "restart" → plain systemctl
        - "reconcile"                  → full lifecycle heal
        - "status"                     → systemctl is-active (read-only)
    """
    bootstrap_job(payload, "cff-stream-control")
    action = payload.action
    stream_id = payload.stream_id
    logger.info("Running stream control: action=%s stream=%s", action, stream_id)

    # Lifecycle path: requires DB row (broadcast prep needs streaming_account_id, etc).
    if action == "reconcile":
        s = _fetch_stream(int(stream_id)) if stream_id else None
        if not s:
            return {"ok": False, "error": f"stream {stream_id} not found"}
        try:
            return {"ok": True, "result": lifecycle.reconcile(s)}
        except Exception as exc:
            logger.exception("Reconcile failed for stream=%s", stream_id)
            telegram.send(f"Stream reconcile failed for {stream_id}: {exc}")
            return {"ok": False, "error": str(exc)}

    # Legacy systemctl-only path.
    unit_name = (payload.metadata or {}).get("unit_name") if hasattr(payload, "metadata") else None
    if not unit_name:
        unit_name = f"stream-{stream_id}"

    if action not in ("start", "stop", "restart", "status"):
        return {"ok": False, "error": f"Invalid action: {action}"}

    try:
        cmd = ["systemctl", action, unit_name]
        logger.info("Executing: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"ok": True, "output": result.stdout}
        raise RuntimeError(f"systemctl {action} {unit_name} failed: {result.stderr}")
    except Exception as exc:
        error = str(exc)
        logger.error("Stream control failed for %s: %s", unit_name, error)
        telegram.send(f"Stream control failed for {unit_name}: {error}")
        return {"ok": False, "error": error}


if __name__ == "__main__":
    from shared.queue.config import QUEUE_STREAM_CONTROL
    from shared.queue.worker_runner import main

    main([QUEUE_STREAM_CONTROL], "cff-stream-control")
