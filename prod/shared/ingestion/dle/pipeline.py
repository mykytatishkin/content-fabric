"""DLE ingestion pipeline: source -> task creation."""

import logging
from datetime import datetime, timedelta
from typing import Any

from shared.db.repositories.task_repo import create_task, get_task_by_dle_id
from shared.ingestion.dle.client import DleClient
from shared.queue.publisher import enqueue_job
from shared.queue.types import DleProcessingPayload
from app.core.config import dle_settings

logger = logging.getLogger(__name__)


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
        """Create a new task in the CFF queue based on DLE post."""
        legacy_info = {
            "dle_source": self.source_slug,
            "dle_post_id": post["id"],
            "dle_post_url": f"https://{self.source_slug.replace('_', '.')}/{post['id']}-{post['alt_name']}.html",
            "normalized": post["normalized"]
        }
        
        # Use DLE title for now. GPT title generation can be a separate step in the worker.
        title = post["title"]
        
        # Schedule slightly in the future to allow processing workers to pick it up.
        scheduled_at = datetime.now() + timedelta(minutes=5)
        
        # source_file_path is empty; DLE processor worker will fill it.
        task_id = create_task(
            channel_id=channel_id,
            source_file_path="", 
            title=title,
            scheduled_at=scheduled_at,
            media_type=media_type,
            legacy_add_info=legacy_info
        )
        logger.info("Created DLE task %s for channel %d (DLE ID: %d)", task_id, channel_id, post["id"])
        
        # Enqueue for DLE processor worker
        try:
            payload = DleProcessingPayload(task_id=task_id)
            enqueue_job("dle_processing", "workers.dle_processor_worker.process_dle_task", payload)
            logger.info("Enqueued task %s for DLE processing", task_id)
        except Exception as e:
            logger.error("Failed to enqueue task %s for DLE processing: %s", task_id, e)
        
        return task_id
