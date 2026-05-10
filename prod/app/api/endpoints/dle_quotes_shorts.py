"""DLE Quotes Shorts API — manual trigger + status of 7 quote pipelines.

URLs:
    GET  /api/v1/dle-quotes-shorts/              → list 7 sources + quote count
    POST /api/v1/dle-quotes-shorts/{slug}/run    → manual enqueue
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_admin
from shared.queue.publisher import enqueue_dle_quotes_shorts
from shared.queue.types import DleQuotesShortsPayload
from shared.ingestion.dle.quotes_shorts import _SITE_TEMPLATES

logger = logging.getLogger(__name__)
router = APIRouter()


# Mirror scheduler/jobs.py mapping
_SLUG_TO_DIR = {
    "audiokniga_one_com": "audiokniga-one.com",
    "knigi_audio_biz":    "unique_audio",
    "club_books_ru":      "club-books.ru",
    "books_online_info":  "books-online.info",
    "slushat_knigi_com":  "slushat-knigi.com",
    "knigi_online_club":  "knigi-online.club",
    "bazaknig_net":       "bazaknig.net",
}

_DEFAULT_CHANNELS = {
    "audiokniga_one_com":   5,
    "knigi_audio_biz":      6,
    "club_books_ru":        21,
    "books_online_info":    23,
    "slushat_knigi_com":    25,
    "knigi_online_club":    12,
    "bazaknig_net":         26,
}


def _base_dir() -> str:
    return os.environ.get(
        "DLE_QUOTES_BASE_DIR",
        "/var/www/fastuser/data/www/aiyoutube.pbnbots.com/data",
    )


def _resolve_paths(slug: str) -> dict[str, str]:
    dir_name = _SLUG_TO_DIR.get(slug, slug)
    base = f"{_base_dir()}/{dir_name}/shorts"
    quotes_file = f"{base}/quotes.txt"
    if slug == "knigi_audio_biz":
        quotes_file = f"{base}/quotes_popadanci.txt"
    return {
        "base": base,
        "quotes_file": quotes_file,
        "backgrounds_dir": f"{base}/backgrounds",
        "bg_music_dir": f"{base}/bg_music",
    }


def _count_lines(path: str) -> int:
    try:
        if not os.path.isfile(path):
            return 0
        with open(path, encoding="utf-8", errors="replace") as f:
            return sum(1 for ln in f if ln.strip())
    except Exception:
        return 0


class DleQuotesRunRequest(BaseModel):
    channel_id: int | None = None  # default per source
    language: str = "ru"


@router.get("/")
def list_sources(_: dict = Depends(get_current_admin)) -> dict[str, Any]:
    items = []
    for slug in _SITE_TEMPLATES.keys():
        paths = _resolve_paths(slug)
        items.append({
            "source_slug": slug,
            "site_name": _SITE_TEMPLATES[slug]["site_name"],
            "default_channel_id": _DEFAULT_CHANNELS.get(slug),
            "quotes_file": paths["quotes_file"],
            "quotes_remaining": _count_lines(paths["quotes_file"]),
            "backgrounds_dir": paths["backgrounds_dir"],
            "backgrounds_count": (
                len([f for f in os.listdir(paths["backgrounds_dir"])
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))])
                if os.path.isdir(paths["backgrounds_dir"]) else 0
            ),
            "bg_music_count": (
                len([f for f in os.listdir(paths["bg_music_dir"])
                     if f.lower().endswith(".mp3")])
                if os.path.isdir(paths["bg_music_dir"]) else 0
            ),
        })
    return {"ok": True, "items": items}


@router.post("/{slug}/run")
def run_source(
    slug: str,
    req: DleQuotesRunRequest,
    _: dict = Depends(get_current_admin),
) -> dict[str, Any]:
    if slug not in _SITE_TEMPLATES:
        raise HTTPException(400, f"unknown source_slug: {slug}")

    channel_id = req.channel_id or _DEFAULT_CHANNELS.get(slug)
    if not channel_id:
        raise HTTPException(400, "channel_id required for this source")

    paths = _resolve_paths(slug)

    payload = DleQuotesShortsPayload(
        source_slug=slug,
        channel_id=channel_id,
        quotes_file=paths["quotes_file"],
        backgrounds_dir=paths["backgrounds_dir"],
        bg_music_dir=paths["bg_music_dir"],
        language=req.language,
    )
    try:
        job_id = enqueue_dle_quotes_shorts(payload)
    except Exception as exc:
        logger.exception("DLE quotes enqueue failed")
        raise HTTPException(500, f"enqueue failed: {exc}")

    return {"ok": True, "job_id": job_id, "source_slug": slug,
            "channel_id": channel_id, "quotes_remaining": _count_lines(paths["quotes_file"])}
