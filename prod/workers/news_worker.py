"""News pipeline worker — RBC RSS → Ken Burns slideshow / vertical short.

1:1 port of Yii ``NewsController::actionUpload_to_youtube`` (long-form,
account=55) and ``NewsController::actionShorts`` (vertical, account=55).

Pipeline:
    1. Fetch first unread RBC RSS item (dedup via news_processed_urls)
    2. Search Google Images via SerpAPI for ``title``, take 5 jpgs >= 1200px
    3. Download images to /tmp
    4. TTS narration (uk language, voice rotates among 4 variants)
    5. Whisper-1 word-level → SRT subtitles
    6. Ken Burns slideshow (long: 1920×1080 / shorts: 1080×1920)
    7. For shorts: burn-in subtitles via shared.video.burn_subtitles
    8. INSERT into Tasks queue
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from shared.db.repositories.task_repo import create_task
from shared.metrics import instrument_job
from shared.news import (
    fetch_first_unread,
    search_images,
    clean_for_tts,
    prepare_text_file,
    align_subtitles,
)
from shared.news.images import download_images
from shared.notifications import telegram
from shared.queue.types import NewsPayload
from shared.tts.openai_tts import synthesize as tts_synthesize
from shared.video import (
    make_long_slideshow,
    make_shorts_slideshow,
    burn_subtitles,
)
from workers._job_bootstrap import bootstrap_job

logger = logging.getLogger(__name__)


# Yii voice variants (NewsController.actionUpload_to_youtube)
_VOICE_VARIANTS = [
    {"gender": "male",   "voice": "fable"},
    {"gender": "male",   "voice": "echo"},
    {"gender": "female", "voice": "alloy"},
    {"gender": "female", "voice": "shimmer"},
]

# News pipeline keywords for hashtag generation (Yii NewsController.keywords)
_NEWS_KEYWORDS = (
    "новини, останні новини, новини сьогодні, свіжі новини, головні новини, "
    "світові новини, міжнародні новини, політика, економіка, фінанси, бізнес новини, "
    "курс валют, інфляція, нафта, газ, енергетика, технології, IT новини, "
    "штучний інтелект, AI новини, війна, конфлікти, геополітика, санкції, "
    "НАТО, ЄС, США, Китай, Росія, Україна, новини України, Київ новини, "
    "новини Європи, новини світу, breaking news, live news, world news, "
    "global news, news update, news today, latest news, current events, "
    "economy news, market news, stock market, oil price, gas price, crypto news, "
    "bitcoin, cryptocurrency, tech news, political news, international news, "
    "trending news, urgent news, headlines, top stories, daily news, news report, "
    "news analysis, news video, youtube news, news shorts, viral news, media news, "
    "journalism, news coverage"
)


def _shuffled_hashtags(count: int = 5) -> str:
    """1:1 port of Yii ``NewsController::return_hashtag``."""
    keywords = [k.strip() for k in _NEWS_KEYWORDS.split(",") if k.strip()]
    random.shuffle(keywords)
    chosen = keywords[:count]
    return " ".join(f"#{k.replace(' ', '_')}" for k in chosen)


@instrument_job("news")
def run_news_job(payload: NewsPayload) -> dict[str, Any]:
    """Fetch new RBC item → 5 photos + TTS + slideshow → INSERT Tasks.

    Returns:
        {ok, task_id?, link?, skipped?, error?}
    """
    bootstrap_job(payload, "cff-news")
    logger.info("Running news job for channel=%d media=%s lang=%s",
                payload.channel_id, payload.media_type, payload.language)

    work_dir = f"/tmp/news_{uuid.uuid4()}"
    os.makedirs(work_dir, exist_ok=True)

    # 1. Fetch RSS
    item = fetch_first_unread(payload.rss_url)
    if not item:
        logger.info("[NEWS] no new items in feed")
        return {"ok": True, "skipped": True, "reason": "no new items"}

    logger.info("[NEWS] processing: %s (%s)", item.title[:80], item.link)

    # 2. Search images
    image_urls = search_images(item.title, count=payload.images_count)
    if len(image_urls) < payload.images_count:
        msg = (f"only {len(image_urls)}/{payload.images_count} images found "
               f"for {item.title!r}")
        logger.warning("[NEWS] %s", msg)
        if not image_urls:
            return {"ok": False, "error": "no images found",
                    "title": item.title, "link": item.link}

    # 3. Download images
    images_dir = os.path.join(work_dir, "images")
    saved = download_images(image_urls, images_dir)
    if not saved:
        return {"ok": False, "error": "no images downloaded",
                "link": item.link}

    # 4. TTS narration
    voice_choice = random.choice(_VOICE_VARIANTS)

    # Long: read fulltext; Shorts: read description (shorter)
    raw_text = item.fulltext if payload.media_type == "video" else item.description
    text_for_tts = clean_for_tts(raw_text)
    if not text_for_tts:
        return {"ok": False, "error": "empty after clean",
                "link": item.link}

    audio_path = os.path.join(work_dir, "audio.mp3")
    try:
        tts_synthesize(
            text_for_tts, audio_path,
            voice=voice_choice["voice"],
            language=payload.language,
            instructions="інформативно, нейтрально, як ведучий новин",
        )
    except Exception as exc:
        logger.exception("[NEWS] TTS failed")
        telegram.send(f"News TTS failed: {exc}")
        return {"ok": False, "error": f"TTS: {exc}", "link": item.link}

    # 5. SRT subtitles (only used for shorts burn-in)
    text_file = os.path.join(work_dir, "text.txt")
    try:
        prepare_text_file(item.title, raw_text, text_file)
    except ValueError as exc:
        logger.warning("[NEWS] prepare_text_file empty: %s", exc)

    srt_path = os.path.join(work_dir, "sub.srt")
    srt_ok = align_subtitles(audio_path, text_for_tts, srt_path)

    # 6. Slideshow
    if payload.media_type == "video":
        # Long 1920×1080 — no subtitles burn-in (Yii original behaviour)
        output_video = os.path.join(work_dir, "youtube_video.mp4")
        ok = make_long_slideshow(saved, audio_path, output_video)
    else:
        # Shorts 1080×1920 + burn-in subtitles if SRT generated
        intermediate = os.path.join(work_dir, "shorts.mp4")
        ok = make_shorts_slideshow(saved, audio_path, intermediate)
        if ok and srt_ok and os.path.isfile(srt_path):
            output_video = os.path.join(work_dir, "shorts_final.mp4")
            ok = burn_subtitles(intermediate, srt_path, output_video)
            if not ok:
                # Fallback to non-burn-in version if subtitle burn fails
                logger.warning("[NEWS] burn_subtitles failed, using shorts.mp4")
                output_video = intermediate
                ok = True
        else:
            output_video = intermediate

    if not ok:
        return {"ok": False, "error": "slideshow assembly failed",
                "link": item.link}

    # 7. INSERT into Tasks queue
    title_with_tags = item.title + " " + _shuffled_hashtags(2)
    description_with_tags = (raw_text or item.description) + " " + _shuffled_hashtags(5)

    # Schedule at "now" for long, +N hours for shorts to spread out
    scheduled = datetime.now()
    if payload.media_type == "shorts":
        scheduled = scheduled + timedelta(hours=2)

    try:
        task_id = create_task(
            channel_id=payload.channel_id,
            source_file_path=output_video,
            title=title_with_tags[:255],
            scheduled_at=scheduled,
            media_type=payload.media_type,
            description=description_with_tags,
            keywords=_shuffled_hashtags(5),
            post_comment="",
            legacy_add_info={
                "source": "rbc_news",
                "link": item.link,
                "pub_date": item.pub_date,
                "voice": voice_choice["voice"],
                "media_type": payload.media_type,
                "trace_id": payload.trace_id,
            },
        )
    except Exception as exc:
        logger.exception("[NEWS] create_task failed")
        return {"ok": False, "error": f"create_task: {exc}",
                "link": item.link}

    logger.info("[NEWS] done: task=%s link=%s media=%s",
                task_id, item.link, payload.media_type)
    return {"ok": True, "task_id": task_id, "link": item.link,
            "media_type": payload.media_type, "voice": voice_choice["voice"]}


if __name__ == "__main__":
    from shared.queue.config import QUEUE_NEWS
    from shared.queue.worker_runner import main

    main([QUEUE_NEWS], "cff-news")
