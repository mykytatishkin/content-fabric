#!/usr/bin/env bash
# Install and enable Content Fabric systemd services.
# Run as root on production server.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SYSTEMD_DIR="${SCRIPT_DIR}/systemd"

echo "==> Copying service files to /etc/systemd/system/ ..."
cp "${SYSTEMD_DIR}"/cff-*.service /etc/systemd/system/

echo "==> Reloading systemd daemon ..."
systemctl daemon-reload

SERVICES=(
    cff-api
    cff-scheduler
    cff-publishing-worker
    cff-notification-worker
    cff-voice-worker
    cff-dle-ingestion-worker
    cff-dle-processor-worker
    cff-shorts-worker
    cff-stats-worker
    cff-stream-control-worker
)

for svc in "${SERVICES[@]}"; do
    echo "==> Enabling ${svc} ..."
    systemctl enable "${svc}"
done

echo ""
echo "Services installed and enabled. To start all:"
echo "  systemctl start cff-api cff-scheduler cff-publishing-worker cff-notification-worker cff-voice-worker cff-dle-ingestion-worker cff-dle-processor-worker cff-shorts-worker cff-stats-worker cff-stream-control-worker"
echo ""
echo "To check status:"
echo "  systemctl status cff-*"
echo ""
echo "NOTE: Stop any nohup processes first:"
echo "  pkill -f 'uvicorn main:app'"
echo "  pkill -f 'scheduler.run'"
echo "  pkill -f 'publishing_worker'"
echo "  pkill -f 'notification_worker'"
echo "  pkill -f 'voice_worker'"
echo "  pkill -f 'dle_ingestion_worker'"
echo "  pkill -f 'dle_processor_worker'"
echo "  pkill -f 'shorts_worker'"
echo "  pkill -f 'stats_worker'"
echo "  pkill -f 'stream_worker'"
