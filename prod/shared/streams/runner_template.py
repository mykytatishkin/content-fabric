"""Bash-шаблоны runner-скриптов и systemd unit'ов для стримов.

Скопировано из Yii: /usr/local/bin/yt_stream_runner.sh + mass_create_streams.sh.
ffmpeg-логика идентична — только Python инфраструктура вокруг.
"""

YT_STREAM_RUNNER = """#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

STREAM_NAME="${STREAM_NAME:-stream}"
STREAM_KEY="${STREAM_KEY:-}"
INPUT_DIR="${INPUT_DIR:-}"
RTMP_HOST="${RTMP_HOST:-a.rtmp.youtube.com}"
RUNTIME_MAX="${RUNTIME_MAX:-42900}"

if [[ -z "$STREAM_KEY" || -z "$INPUT_DIR" ]]; then
  echo "ERROR: STREAM_KEY or INPUT_DIR is empty"
  exit 2
fi

PLAYLIST="$INPUT_DIR/playlist.txt"
RTMP_URL="rtmp://${RTMP_HOST}/live2/${STREAM_KEY}"

echo "== ${STREAM_NAME} =="
echo "STREAM_KEY: ${STREAM_KEY:0:6}***"
echo "INPUT_DIR:  ${INPUT_DIR}"
echo "RTMP_HOST:  ${RTMP_HOST}"
echo "RUNTIME:    ${RUNTIME_MAX}"

mkdir -p "$INPUT_DIR"
cd "$INPUT_DIR"

shopt -s nullglob
: > "$PLAYLIST"
for f in $(ls -1 *.mp4 2>/dev/null | sort); do
  echo "file '${PWD}/${f}'" >> "$PLAYLIST"
done

if [[ ! -s "$PLAYLIST" ]]; then
  echo "ERROR: playlist is empty (no *.mp4 in ${INPUT_DIR})"
  exit 3
fi

exec ffmpeg -hide_banner -loglevel info -nostdin -re \\
  -f concat -safe 0 -stream_loop -1 -i "$PLAYLIST" \\
  -fflags +genpts -avoid_negative_ts make_zero \\
  -c:v copy -c:a copy \\
  -t "$RUNTIME_MAX" \\
  -f flv "$RTMP_URL"
"""


def render_env_file(stream_name: str, stream_key: str, input_dir: str,
                    rtmp_host: str = "a.rtmp.youtube.com",
                    runtime_max: int = 42900) -> str:
    """Содержимое /etc/aiyoutube/streams/<name>.env."""
    return (
        f"STREAM_NAME={stream_name}\n"
        f"STREAM_KEY={stream_key}\n"
        f"INPUT_DIR={input_dir}\n"
        f"RTMP_HOST={rtmp_host}\n"
        f"RUNTIME_MAX={runtime_max}\n"
    )


def render_systemd_unit(stream_name: str, service_name: str, workdir: str,
                        env_file: str, runner_path: str) -> str:
    """Содержимое /etc/systemd/system/stream-<name>.service."""
    return f"""[Unit]
Description=YouTube Stream: {stream_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={workdir}
EnvironmentFile={env_file}

ExecStart=/usr/bin/env bash {runner_path}

# systemd керує перезапуском тільки якщо впав
Restart=on-failure
RestartSec=5

KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=60
SuccessExitStatus=0 130 255

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
