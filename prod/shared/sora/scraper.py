"""Scraper for Sora AI public feed using Zenrows."""

import logging
import requests
from typing import Any

from app.core.config import api_settings

logger = logging.getLogger(__name__)


def fetch_sora_feed(url: str = "https://sora.chatgpt.com/backend/public/nf2/feed") -> list[dict[str, Any]]:
    """Fetch Sora public feed using Zenrows proxy."""
    if not api_settings.ZENROWS_API_KEY:
        logger.error("ZENROWS_API_KEY not set")
        return []

    proxy_url = "https://api.zenrows.com/v1/"
    params = {
        "apikey": api_settings.ZENROWS_API_KEY,
        "url": url,
        "js_render": "true"
    }

    try:
        logger.info("Fetching Sora feed via Zenrows")
        response = requests.get(proxy_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    except Exception as e:
        logger.error("Failed to fetch Sora feed: %s", e)
        return []


def download_sora_video(video_url: str, output_path: str) -> bool:
    """Download Sora video."""
    try:
        logger.info("Downloading Sora video: %s → %s", video_url, output_path)
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error("Failed to download Sora video: %s", e)
        return False
