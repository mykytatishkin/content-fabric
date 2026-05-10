"""DLE Quotes Shorts worker — RQ consumer for QUEUE_DLE_QUOTES_SHORTS.

Replaces all 7 Yii ``actionShorts`` controllers (Audiokniga, Bazaknig,
Books_online_info, Club_books_ru, Knigi_online_club, Slushat_knigi_com,
Unique_audio).

Job: pop one quote from `quotes.txt` → TTS + ASS + 1080×1920 short →
INSERT into Tasks queue scheduled at 09:00 today (Yii default).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, time as dt_time, timedelta
from typing import Any

from shared.db.repositories.task_repo import create_task
from shared.ingestion.dle.quotes_shorts import process_quote_short
from shared.metrics import instrument_job
from shared.notifications import telegram
from shared.queue.types import DleQuotesShortsPayload
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


def _next_09_00() -> datetime:
    """Yii default for DLE shorts: schedule at today's 09:00.

    If 09:00 already passed today — schedule for tomorrow's 09:00.
    """
    now = datetime.now()
    today_9 = datetime.combine(now.date(), dt_time(9, 0))
    if now >= today_9:
        return today_9 + timedelta(days=1)
    return today_9


@instrument_job("dle_quotes_shorts")
def run_dle_quotes_shorts_job(payload: DleQuotesShortsPayload) -> dict[str, Any]:
    """Process one quote → 1080×1920 short → Tasks INSERT.

    Returns:
        {ok: bool, task_id?: int, source_slug, error?: str}
    """
    bootstrap_job(payload, "cff-dle-quotes-shorts")
    logger.info("Running DLE quotes shorts: source=%s channel=%d",
                payload.source_slug, payload.channel_id)

    work_dir = f"/tmp/dle_quotes_{payload.source_slug}_{uuid.uuid4()}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        meta = process_quote_short(
            source_slug=payload.source_slug,
            quotes_file=payload.quotes_file,
            backgrounds_dir=payload.backgrounds_dir,
            bg_music_dir=payload.bg_music_dir,
            output_dir=work_dir,
            language=payload.language,
        )
    except Exception as exc:
        logger.exception("DLE quotes shorts crashed for %s", payload.source_slug)
        telegram.send(f"DLE quotes shorts failed for {payload.source_slug}: {exc}")
        return {"ok": False, "error": str(exc), "source_slug": payload.source_slug}

    if not meta:
        return {"ok": True, "skipped": True, "reason": "no quotes left or TTS failed",
                "source_slug": payload.source_slug}

    # Insert into Tasks queue with date_post = next 09:00
    try:
        task_id = create_task(
            channel_id=payload.channel_id,
            source_file_path=meta["att_file_path"],
            title=meta["title"],
            scheduled_at=_next_09_00(),
            media_type="shorts",
            description=meta["description"],
            keywords=meta["keywords"],
            post_comment=meta["post_comment"],
            legacy_add_info={
                "source": "dle_quotes_shorts",
                "source_slug": meta["source_slug"],
                "voice": meta["voice"],
                "style": meta["style"],
                "audio_duration_sec": meta["audio_duration_sec"],
                "quote": meta["quote"],
                "trace_id": payload.trace_id,
            },
        )
    except Exception as exc:
        logger.exception("Failed to create task for DLE quotes shorts")
        return {"ok": False, "error": f"create_task failed: {exc}",
                "source_slug": payload.source_slug}

    logger.info("DLE quotes shorts done: source=%s task=%s",
                payload.source_slug, task_id)
    return {"ok": True, "task_id": task_id, "source_slug": payload.source_slug,
            "voice": meta["voice"], "style": meta["style"]}


if __name__ == "__main__":
    from shared.queue.config import QUEUE_DLE_QUOTES_SHORTS
    from shared.queue.worker_runner import main

    main([QUEUE_DLE_QUOTES_SHORTS], "cff-dle-quotes-shorts")
