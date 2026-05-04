"""YouTube video downloader using yt-dlp."""

import logging
import os
import subprocess
from typing import Any

from app.core.config import api_settings

logger = logging.getLogger(__name__)


def download_video(url: str, output_path: str) -> bool:
    """Download a YouTube video using yt-dlp with configured cookies."""
    cookies_path = api_settings.YOUTUBE_COOKIES_PATH
    
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        url
    ]
    
    if os.path.exists(cookies_path):
        cmd.extend(["--cookies", cookies_path])
    else:
        logger.warning("YouTube cookies file not found at %s", cookies_path)

    try:
        logger.info("Downloading video: %s → %s", url, output_path)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to download video %s: %s", url, e.stderr)
        return False
