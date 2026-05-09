"""DLE ingestion pipeline: source -> task creation."""

import logging
from datetime import datetime, timedelta
from typing import Any

from shared.db.repositories.task_repo import create_task, get_task_by_dle_id
from shared.ingestion.dle.client import DleClient
from shared.logging_context import ensure_trace_id
from shared.queue.publisher import enqueue_job
from shared.queue.types import DleProcessingPayload
from app.core.config import dle_settings

logger = logging.getLogger(__name__)


def slug_to_host(slug: str) -> str:
    """Convert source_slug to its host: 'audiokniga_one_com' → 'audiokniga-one.com'.

    Last underscore-separated part is the TLD (joined with '.'); the rest is
    joined with '-'. Single-token slugs are returned as-is.
    """
    parts = slug.split("_")
    if len(parts) < 2:
        return slug
    return "-".join(parts[:-1]) + "." + parts[-1]


class DleIngestionPipeline:
    def __init__(self, source_slug: str):
        self.source_slug = source_slug
        self.dsn = dle_settings.all_sources().get(source_slug)
        if not self.dsn:
            raise ValueError(f"No DSN found for DLE source: {source_slug}")
        self.client = DleClient(self.dsn, source_slug)

    def run(self, channel_id: int, limit: int = 1, media_type: str = "video") -> int:
        """Run ingestion for one source and one channel.
        
        Returns the number of tasks created.
        """
        logger.info("[DLE PIPELINE] Starting ingestion: source=%s, channel=%d, limit=%d, media=%s", 
                    self.source_slug, channel_id, limit, media_type)
        
        try:
            posts = self.client.fetch_recent_posts(limit=limit)
            logger.debug("[DLE PIPELINE] Fetched %d posts from %s", len(posts), self.source_slug)
        except Exception as e:
            logger.error("[DLE PIPELINE] CRITICAL: Failed to fetch posts from %s: %s", self.source_slug, e)
            return 0
        
        count = 0
        for i, post in enumerate(posts):
            post_id = post.get("id")
            title = post.get("title")
            logger.debug("[DLE PIPELINE] Processing post [%d/%d]: ID=%s, Title='%s'", 
                         i+1, len(posts), post_id, title)
            
            if self._is_already_processed(post_id):
                logger.info("[DLE PIPELINE] SKIP: Post %s already exists in CFF tasks", post_id)
                continue
            
            logger.info("[DLE PIPELINE] NEW POST detected: ID=%s. Creating CFF task...", post_id)
            try:
                task_id = self._create_cff_task(post, channel_id, media_type)
                if task_id:
                    count += 1
                    logger.info("[DLE PIPELINE] SUCCESS: Task %d created for post %s", task_id, post_id)
                else:
                    logger.warning("[DLE PIPELINE] FAILED to create task for post %s", post_id)
            except Exception as e:
                logger.exception("[DLE PIPELINE] EXCEPTION during task creation for post %s: %s", post_id, e)
                
        logger.info("[DLE PIPELINE] Ingestion complete: %s -> %d tasks created", self.source_slug, count)
        return count

    def _is_already_processed(self, dle_post_id: int) -> bool:
        """Check if this post was already imported into CFF."""
        return get_task_by_dle_id(self.source_slug, dle_post_id) is not None

    def _create_cff_task(self, post: dict[str, Any], channel_id: int, media_type: str) -> int | None:
        """Create a new task in the CFF queue based on DLE post.

        Generates a per-task trace_id which is:
          - stored in legacy_add_info.trace_id (queryable from DB)
          - set as logging context for the rest of this call
          - propagated into the DleProcessingPayload → all downstream workers
        """
        # One trace_id per CFF task — uniquely identifies the path through every worker.
        # Reuse a parent trace_id (set by an upstream caller) if present; otherwise
        # mint a new one. ensure_trace_id() handles both cases.
        trace_id = ensure_trace_id()

        legacy_info = {
            "dle_source": self.source_slug,
            "dle_post_id": post["id"],
            "dle_post_url": f"https://{slug_to_host(self.source_slug)}/{post['id']}-{post['alt_name']}.html",
            "normalized": post["normalized"],
            # Per-source URL builders (sources.py) need raw xfields + book_id
            # to mirror the PHP controllers (e.g. tr_id, baza_knig_info_id,
            # wallpaper, book_id for redirectto.cc playlist).
            "xfields_parsed": post.get("xfields_parsed") or {},
            "book_id": post.get("book_id"),
            "trace_id": trace_id,
        }

        title = post["title"]
        scheduled_at = datetime.now() + timedelta(minutes=5)

        task_id = create_task(
            channel_id=channel_id,
            source_file_path="",
            title=title,
            scheduled_at=scheduled_at,
            media_type=media_type,
            legacy_add_info=legacy_info,
        )
        logger.info("Created DLE task %s for channel %d (DLE ID: %d) trace_id=%s",
                    task_id, channel_id, post["id"], trace_id)

        try:
            payload = DleProcessingPayload(task_id=task_id, trace_id=trace_id)
            enqueue_job("dle_processing", "workers.dle_processor_worker.process_dle_task", payload)
            logger.info("Enqueued task %s for DLE processing trace_id=%s", task_id, trace_id)
        except Exception as e:
            logger.error("Failed to enqueue task %s for DLE processing: %s", task_id, e)

        return task_id
