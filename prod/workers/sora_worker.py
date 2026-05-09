"""Sora AI worker — rq worker consuming from 'sora' queue.

Replaces Yii's `php yii sora/get_video --channel-id=N`. Fetches the Sora public
feed, filters out already-seen posts (tracked in `sora_used_posts`), downloads
each new video to /tmp, and enqueues a ShortsPayload for downstream processing.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from shared.db.repositories import sora_repo
from shared.metrics import instrument_job
from shared.notifications import telegram
from shared.queue.publisher import enqueue_shorts
from shared.queue.types import ShortsPayload, SoraPayload
from shared.sora import scraper
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


def _extract_post_fields(item: dict[str, Any]) -> tuple[str | None, str | None, int]:
    """Pull (post_id, video_url, views) out of a single feed item.

    Sora feed shape (from legacy SoraController):
      item["post"]["id"]
      item["post"]["attachments"][0]["url"]
      item["post"]["unique_view_count"]
    """
    post = item.get("post") or item
    post_id = post.get("id")
    attachments = post.get("attachments") or []
    video_url = None
    if attachments and isinstance(attachments, list):
        first = attachments[0]
        if isinstance(first, dict):
            video_url = first.get("url")
    views = int(post.get("unique_view_count") or post.get("views") or 0)
    return post_id, video_url, views


@instrument_job("sora")
def run_sora_job(payload: SoraPayload) -> dict[str, Any]:
    """Fetch Sora feed → download new videos → enqueue Shorts jobs."""
    bootstrap_job(payload, "cff-sora")
    logger.info("Running Sora job for channel %d (limit=%d, media_type=%s)",
                payload.channel_id, payload.limit, payload.media_type)

    try:
        items = scraper.fetch_sora_feed(payload.feed_url)
    except Exception as exc:
        logger.exception("Sora feed fetch raised")
        telegram.send(f"Sora feed fetch failed: {exc}")
        return {"ok": False, "error": str(exc), "fetched": 0, "new": 0, "queued": 0}

    fetched = len(items)
    logger.info("Sora feed: fetched %d items", fetched)

    if not items:
        return {"ok": True, "fetched": 0, "new": 0, "queued": 0}

    used_ids = sora_repo.get_used_post_ids()
    queued = 0
    new_count = 0

    for item in items:
        if queued >= payload.limit:
            break

        post_id, video_url, views = _extract_post_fields(item)
        if not post_id or not video_url:
            logger.debug("Sora: skipping malformed item: %r", item)
            continue
        if post_id in used_ids:
            continue
        if views < payload.min_views:
            logger.debug("Sora: skipping post %s (views=%d < min=%d)",
                         post_id, views, payload.min_views)
            continue

        new_count += 1

        tmp_dir = f"/tmp/shorts_{uuid.uuid4()}"
        try:
            os.makedirs(tmp_dir, exist_ok=True)
        except Exception:
            logger.exception("Sora: failed to create tmp dir %s", tmp_dir)
            continue

        out_path = os.path.join(tmp_dir, "source.mp4")
        try:
            ok = scraper.download_sora_video(video_url, out_path)
        except Exception:
            logger.exception("Sora: download raised for %s", post_id)
            ok = False
        if not ok:
            logger.warning("Sora: download failed for post %s (%s)", post_id, video_url)
            continue

        try:
            enqueue_shorts(ShortsPayload(
                channel_id=payload.channel_id,
                donor_video_url=out_path,
                limit=1,
                metadata={
                    "source": "sora",
                    "sora_post_id": post_id,
                    "media_type": payload.media_type,
                },
            ))
            queued += 1
            sora_repo.mark_post_used(post_id, channel_id=payload.channel_id)
            logger.info("Sora: queued shorts job for post %s (channel=%d)",
                        post_id, payload.channel_id)
        except Exception:
            logger.exception("Sora: enqueue_shorts failed for post %s", post_id)

    logger.info("Sora job done: fetched=%d new=%d queued=%d",
                fetched, new_count, queued)
    return {"ok": True, "fetched": fetched, "new": new_count, "queued": queued}


if __name__ == "__main__":
    from shared.queue.config import QUEUE_SORA
    from shared.queue.worker_runner import main
    main([QUEUE_SORA], "cff-sora")
