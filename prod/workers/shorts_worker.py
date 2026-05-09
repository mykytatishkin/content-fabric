"""Shorts processing worker — rq worker consuming from 'shorts' queue."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from shared.queue.types import ShortsPayload
from shared.shorts.downloader import download_video
from shared.shorts.transcriber import transcribe_with_timestamps
from shared.shorts.highlight import find_highlights
from shared.shorts.cutter import cut_segment
from shared.shorts.thumbnail import extract_frames, pick_best_thumbnail
from shared.db.repositories.task_repo import create_task
from shared.metrics import instrument_job
from shared.notifications import telegram
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


@instrument_job("shorts")
def run_shorts_job(payload: ShortsPayload) -> dict[str, Any]:
    """Job handler called by rq.

    1. Download donor video.
    2. Transcribe using Whisper.
    3. Find highlights using GPT-4.
    4. For each highlight:
       - Cut segment vertical.
       - Pick thumbnail.
       - Create CFF task (ready for upload).
    """
    bootstrap_job(payload, "cff-shorts")
    logger.info("Running shorts job for channel %d", payload.channel_id)
    
    tmp_dir = f"/tmp/shorts_{uuid.uuid4()}"
    os.makedirs(tmp_dir, exist_ok=True)
    
    video_path = os.path.join(tmp_dir, "donor_video.mp4")
    
    try:
        # 1. Download
        if not download_video(payload.donor_video_url, video_path):
            raise Exception("Failed to download donor video")
            
        # 2. Transcribe
        transcript = transcribe_with_timestamps(video_path)
        if not transcript:
            raise Exception("Failed to transcribe video")
            
        # 3. Highlights
        highlights = find_highlights(transcript, limit=payload.limit)
        logger.info("Found %d highlights", len(highlights))
        
        created_tasks = 0
        for i, h in enumerate(highlights):
            output_f = os.path.join(tmp_dir, f"short_{i}.mp4")
            
            # 4. Cut
            if cut_segment(video_path, output_f, h["start"], h["end"], format_type="VERT"):
                # 5. Thumbnail
                frame_dir = os.path.join(tmp_dir, f"frames_{i}")
                frames = extract_frames(output_f, frame_dir)
                thumb_path = pick_best_thumbnail(frames)
                
                # 6. Create Task
                from datetime import datetime, timedelta
                task_id = create_task(
                    channel_id=payload.channel_id,
                    source_file_path=output_f,
                    title=h["title"],
                    scheduled_at=datetime.now() + timedelta(hours=i*2),
                    media_type="shorts",
                    thumbnail_path=thumb_path,
                    description=h.get("reason", "Generated short"),
                    legacy_add_info={"donor_url": payload.donor_video_url, "highlight_index": i}
                )
                if task_id:
                    created_tasks += 1
                    
        return {"ok": True, "created_tasks": created_tasks}
    except Exception as exc:
        error = str(exc)
        logger.error("Shorts job failed: %s", error)
        telegram.send(f"Shorts job failed for channel {payload.channel_id}: {error}")
        return {"ok": False, "error": error}
    finally:
        # Cleanup should probably be delayed until tasks are COMPLETED
        # or we move files to a persistent storage.
        pass


if __name__ == "__main__":
    import shared.env  # noqa: F401 — load .env files

    from rq import Worker

    from shared.queue.config import get_redis, QUEUE_SHORTS

    from shared.logging_config import setup_logging
    setup_logging(service_name="cff-shorts")
    redis_conn = get_redis()
    worker = Worker([QUEUE_SHORTS], connection=redis_conn)
    worker.work()
