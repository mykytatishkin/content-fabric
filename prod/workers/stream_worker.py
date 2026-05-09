"""Stream control worker — manages systemd units for 9 YouTube streams."""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from shared.metrics import instrument_job
from shared.queue.types import StreamControlPayload
from shared.notifications import telegram
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


@instrument_job("stream-control")
def run_stream_control_job(payload: StreamControlPayload) -> dict[str, Any]:
    """Job handler called by rq.

    action: "start" | "stop" | "restart" | "status"
    stream_id: ID from live_stream_configurations
    """
    bootstrap_job(payload, "cff-stream-control")
    logger.info("Running stream control: action=%s stream=%s", payload.action, payload.stream_id)
    
    # Map stream_id to systemd unit name
    # In a real scenario, we would fetch the slug from the DB
    # For now, let's assume payload.metadata contains the unit name
    unit_name = payload.metadata.get("unit_name")
    if not unit_name:
        # Fallback search by ID (simplified)
        unit_name = f"stream-{payload.stream_id}"

    if payload.action not in ["start", "stop", "restart", "status"]:
        return {"ok": False, "error": f"Invalid action: {payload.action}"}

    try:
        cmd = ["systemctl", payload.action, unit_name]
        logger.info("Executing: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return {"ok": True, "output": result.stdout}
        else:
            raise Exception(f"Systemd failed: {result.stderr}")
            
    except Exception as exc:
        error = str(exc)
        logger.error("Stream control failed for %s: %s", unit_name, error)
        telegram.send(f"Stream control failed for {unit_name}: {error}")
        return {"ok": False, "error": error}


if __name__ == "__main__":
    from shared.queue.config import QUEUE_STREAM_CONTROL
    from shared.queue.worker_runner import main
    main([QUEUE_STREAM_CONTROL], "cff-stream-control")
