"""SerpAPI Google Images search — 1:1 port of Yii ``rest_api_search_images``.

Filter: original_width >= 1200, jpg only, take 5.
Fallback: Google Custom Search API (``googleImagesSearch``).
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_SERPAPI_BASE = "https://serpapi.com/search.json"
_GOOGLE_CS_BASE = "https://www.googleapis.com/customsearch/v1"
_DEFAULT_TIMEOUT = 30


def _get_extension_from_url(url: str) -> str:
    """Extract lowercase file extension from URL path (no leading dot)."""
    path = urlparse(url).path
    return os.path.splitext(path)[1].lower().lstrip(".")


def search_images_serpapi(
    query: str,
    *,
    api_key: str | None = None,
    min_width: int = 1200,
    count: int = 5,
    language: str = "en",
    geo: str = "us",
) -> list[str]:
    """SerpAPI Google Images search. Returns up to ``count`` URLs of jpg images
    with ``original_width >= min_width``.

    Yii equivalent: ``NewsController::rest_api_search_images($q)``.
    """
    api_key = api_key or os.environ.get("SERPAPI_KEY")
    if not api_key:
        logger.error("[NEWS IMG] SERPAPI_KEY not set")
        return []

    params = {
        "engine": "google_images",
        "q": query,
        "google_domain": "google.com",
        "hl": language,
        "gl": geo,
        "api_key": api_key,
    }
    try:
        resp = requests.get(_SERPAPI_BASE, params=params, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("[NEWS IMG] SerpAPI fetch failed: %s", exc)
        return []

    images_results = data.get("images_results") or []
    out: list[str] = []
    for img in images_results:
        if img.get("original_width", 0) < min_width:
            continue
        url = img.get("original")
        if not url:
            continue
        if _get_extension_from_url(url) not in ("jpg", "jpeg"):
            continue
        out.append(url)
        if len(out) >= count:
            break

    logger.info("[NEWS IMG] SerpAPI: query=%r → %d images (>= %dpx)",
                query, len(out), min_width)
    return out


def search_images_google_cs(
    query: str,
    *,
    api_key: str | None = None,
    cx: str | None = None,
    count: int = 3,
) -> list[str]:
    """Google Custom Search Images — 1:1 port of Yii ``googleImagesSearch``.

    Used as fallback when SerpAPI is rate-limited or unavailable.
    """
    api_key = api_key or os.environ.get("GOOGLE_API_KEY_NEWS")
    cx = cx or os.environ.get("GOOGLE_CX_NEWS")
    if not api_key or not cx:
        logger.error("[NEWS IMG] GOOGLE_API_KEY_NEWS / GOOGLE_CX_NEWS not set")
        return []

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": min(count, 10),
        "safe": "active",
        "imgSize": "large",
        "fileType": "jpg",
        "rights": "cc_publicdomain,cc_attribute,cc_sharealike",
    }
    try:
        resp = requests.get(_GOOGLE_CS_BASE, params=params, timeout=_DEFAULT_TIMEOUT,
                            headers={"User-Agent": "CFF-news-pipeline/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("[NEWS IMG] Google CS fetch failed: %s", exc)
        return []

    items = data.get("items") or []
    return [it["link"] for it in items if it.get("link")][:count]


def search_images(query: str, count: int = 5) -> list[str]:
    """Try SerpAPI first, fallback to Google Custom Search.

    Returns up to ``count`` image URLs. Empty list on full failure.
    """
    urls = search_images_serpapi(query, count=count)
    if len(urls) >= count:
        return urls

    needed = count - len(urls)
    logger.info("[NEWS IMG] SerpAPI returned %d, need %d more — falling back to Google CS",
                len(urls), needed)
    fallback = search_images_google_cs(query, count=needed)
    return (urls + fallback)[:count]


def download_images(urls: list[str], output_dir: str) -> list[str]:
    """Download URLs → ``output_dir/{1..N}.jpg``. Returns successful paths."""
    os.makedirs(output_dir, exist_ok=True)
    saved: list[str] = []
    for i, url in enumerate(urls, start=1):
        path = os.path.join(output_dir, f"{i}.jpg")
        try:
            resp = requests.get(url, timeout=_DEFAULT_TIMEOUT,
                                headers={"User-Agent": "Mozilla/5.0"})
            ctype = resp.headers.get("Content-Type", "").lower()
            if resp.status_code != 200 or "image/" not in ctype:
                logger.warning("[NEWS IMG] skip %s (status=%d type=%s)",
                               url, resp.status_code, ctype)
                continue
            with open(path, "wb") as f:
                f.write(resp.content)
            saved.append(path)
        except Exception as exc:
            logger.warning("[NEWS IMG] download failed %s: %s", url, exc)
    logger.info("[NEWS IMG] downloaded %d/%d to %s", len(saved), len(urls), output_dir)
    return saved
