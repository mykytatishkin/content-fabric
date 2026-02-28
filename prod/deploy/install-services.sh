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
)

for svc in "${SERVICES[@]}"; do
    echo "==> Enabling ${svc} ..."
    systemctl enable "${svc}"
done

echo ""
echo "Services installed and enabled. To start all:"
echo "  systemctl start cff-api cff-scheduler cff-publishing-worker cff-notification-worker cff-voice-worker"
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
