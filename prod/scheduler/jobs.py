"""Scheduler job definitions — poll DB and enqueue to Redis."""

from __future__ import annotations

import logging

from shared.db.models import TaskStatus
from shared.db.repositories import task_repo, channel_repo, console_repo, stats_repo
from shared.queue.publisher import (
    enqueue_video_upload,
    enqueue_dle_ingestion,
    enqueue_shorts,
    enqueue_sora,
    enqueue_voice_change,
)
from shared.queue.types import (
    VideoUploadPayload,
    DleIngestionPayload,
    ShortsPayload,
    SoraPayload,
    VoiceChangePayload,
)
from shared.youtube.token_refresh import build_credentials, ensure_fresh_credentials

logger = logging.getLogger(__name__)


def enqueue_pending_tasks() -> int:
    """Find pending tasks (status=0, scheduled_at <= NOW) and push to Redis.

    Returns the number of tasks enqueued.
    """
    logger.debug("[SCHEDULER] Polling for pending tasks...")
    tasks = task_repo.get_pending_tasks(limit=50)
    if not tasks:
        logger.debug("[SCHEDULER] 0 pending tasks found")
        return 0
    
    logger.info("[SCHEDULER] Found %d pending tasks to enqueue", len(tasks))

    count = 0
    for t in tasks:
        task_id = t.get("id")
        channel_id = t.get("channel_id")
        media_type = t.get("media_type")
        
        try:
            # Routing logic:
            # 1. If source_file_path is empty but it's a DLE task -> route to voice/processing
            # 2. Otherwise -> route to publishing
            
            legacy = t.get("legacy_add_info") or {}
            is_dle = isinstance(legacy, dict) and "dle_source" in legacy
            
            logger.debug("[SCHEDULER] Evaluating task %d (channel=%d, media=%s, is_dle=%s)", 
                         task_id, channel_id, media_type, is_dle)
            
            if not t.get("source_file_path") and is_dle:
                logger.info("[SCHEDULER] ROUTING: DLE task %d -> [VOICE/PROCESSING QUEUE]", task_id)
                task_repo.mark_task_processing(task_id)
                enqueue_voice_change(VoiceChangePayload(
                    task_id=task_id,
                    source_file_path="",  # Worker will download based on legacy_add_info
                    output_file_path="",  # Worker will decide output path
                    metadata={"is_dle": True}
                ))
                count += 1
                logger.debug("[SCHEDULER] Task %d enqueued to voice queue", task_id)
                continue

            # Standard upload path
            logger.info("[SCHEDULER] ROUTING: Task %d -> [PUBLISHING QUEUE]", task_id)
            task_repo.mark_task_processing(task_id)
            enqueue_video_upload(VideoUploadPayload(
                task_id=task_id,
                channel_id=channel_id,
                source_file_path=t["source_file_path"] or "",
                title=t["title"] or "",
                description=t.get("description"),
                keywords=t.get("keywords"),
                thumbnail_path=t.get("thumbnail_path"),
                post_comment=t.get("post_comment"),
                media_type=media_type or "video",
            ))
            count += 1
            logger.info("[SCHEDULER] SUCCESS: Task %d enqueued for channel %d", task_id, channel_id)
        except Exception as e:
            logger.error("[SCHEDULER] FAILED to enqueue task %d: %s", task_id, e)
            # Reset back to pending so it can be retried
            task_repo.update_task_status(task_id, TaskStatus.PENDING.value)

    if count > 0:
        logger.info("[SCHEDULER] Evaluation complete: %d tasks successfully routed", count)
    return count


def validate_channel_tokens() -> tuple[int, int]:
    """Try to refresh credentials for all enabled channels with tokens.

    Returns (success_count, failure_count).
    """
    channels = channel_repo.get_channels_with_tokens()
    if not channels:
        logger.info("Token validation: no channels with tokens found")
        return 0, 0

    success = 0
    failure = 0
    for ch in channels:
        try:
            console = console_repo.get_console_by_id(ch["console_id"])
            if not console:
                logger.warning("Channel %s (%s): console_id=%s not found",
                               ch["id"], ch["name"], ch["console_id"])
                channel_repo.update_token_check(ch["id"], ok=False)
                failure += 1
                continue

            creds = build_credentials(
                access_token=ch["access_token"],
                refresh_token=ch["refresh_token"],
                client_id=console["client_id"],
                client_secret=console["client_secret"],
                token_expires_at=ch["token_expires_at"],
            )
            ensure_fresh_credentials(creds, channel_id=ch["id"])
            channel_repo.update_token_check(ch["id"], ok=True)
            success += 1
            logger.info("Token OK: channel %s (%s)", ch["id"], ch["name"])
        except Exception:
            logger.exception("Token FAILED: channel %s (%s)", ch["id"], ch["name"])
            channel_repo.update_token_check(ch["id"], ok=False)
            failure += 1

    logger.info("Token validation: %d ok, %d failed", success, failure)
    return success, failure


def collect_channel_stats() -> tuple[int, int]:
    """Fetch YouTube channel statistics for all channels and store daily snapshots.

    Uses YouTube Data API v3 (API key, no OAuth needed).
    Returns (success_count, failure_count).
    """
    from app.core.config import api_settings

    api_key = api_settings.YOUTUBE_API_KEY
    if not api_key:
        logger.warning("Stats collection skipped: YOUTUBE_API_KEY not set")
        return 0, 0

    channels = channel_repo.get_all_channels(enabled_only=True)
    if not channels:
        logger.info("Stats collection: no enabled channels")
        return 0, 0

    from googleapiclient.discovery import build as yt_build
    youtube = yt_build("youtube", "v3", developerKey=api_key)

    success = 0
    failure = 0

    # Batch channels in groups of 50 (API limit per request)
    batch_size = 50
    for i in range(0, len(channels), batch_size):
        batch = channels[i:i + batch_size]
        channel_ids = [ch["platform_channel_id"] for ch in batch]
        # Map platform_channel_id -> our channel record
        ch_map = {ch["platform_channel_id"]: ch for ch in batch}

        try:
            response = youtube.channels().list(
                part="statistics",
                id=",".join(channel_ids),
                maxResults=batch_size,
            ).execute()

            for item in response.get("items", []):
                yt_id = item["id"]
                stats = item.get("statistics", {})
                ch = ch_map.get(yt_id)
                if not ch:
                    continue
                try:
                    stats_repo.record_stats(
                        channel_id=ch["id"],
                        platform_channel_id=yt_id,
                        subscribers=int(stats.get("subscriberCount", 0)),
                        views=int(stats.get("viewCount", 0)),
                        videos=int(stats.get("videoCount", 0)),
                    )
                    success += 1
                except Exception:
                    logger.exception("Failed to record stats for channel %s (%s)", ch["id"], ch["name"])
                    failure += 1

        except Exception:
            logger.exception("YouTube API batch request failed for channels %d-%d", i, i + len(batch))
            failure += len(batch)

    logger.info("Stats collection: %d ok, %d failed", success, failure)
    return success, failure


def collect_video_stats() -> tuple[int, int]:
    """Fetch YouTube video statistics for all completed uploads.

    Uses YouTube Data API v3 (API key, no OAuth needed).
    Returns (success_count, failure_count).
    """
    from app.core.config import api_settings

    api_key = api_settings.YOUTUBE_API_KEY
    if not api_key:
        logger.warning("Video stats collection skipped: YOUTUBE_API_KEY not set")
        return 0, 0

    tasks = stats_repo.get_completed_tasks_with_upload_id()
    if not tasks:
        logger.info("Video stats collection: no completed tasks with upload_id")
        return 0, 0

    from googleapiclient.discovery import build as yt_build
    youtube = yt_build("youtube", "v3", developerKey=api_key)

    success = 0
    failure = 0

    # Map upload_id -> task record
    task_map = {t["upload_id"]: t for t in tasks}
    upload_ids = list(task_map.keys())

    # Batch in groups of 50
    batch_size = 50
    for i in range(0, len(upload_ids), batch_size):
        batch = upload_ids[i:i + batch_size]
        try:
            response = youtube.videos().list(
                part="statistics",
                id=",".join(batch),
                maxResults=batch_size,
            ).execute()

            for item in response.get("items", []):
                vid = item["id"]
                s = item.get("statistics", {})
                t = task_map.get(vid)
                if not t:
                    continue
                try:
                    stats_repo.record_video_stats(
                        task_id=t["id"],
                        channel_id=t["channel_id"],
                        upload_id=vid,
                        views=int(s.get("viewCount", 0)),
                        likes=int(s.get("likeCount", 0)),
                        dislikes=int(s.get("dislikeCount", 0)),
                        comments=int(s.get("commentCount", 0)),
                        favorites=int(s.get("favoriteCount", 0)),
                    )
                    success += 1
                except Exception:
                    logger.exception("Failed to record video stats for task %s (video %s)", t["id"], vid)
                    failure += 1

        except Exception:
            logger.exception("YouTube API video stats batch request failed for batch %d-%d", i, i + len(batch))
            failure += len(batch)

    logger.info("Video stats collection: %d ok, %d failed", success, failure)
    return success, failure


# ─── Yii migration: периодические задачи (feat/yii-integration) ──────
#
# Маппинг повторяет Yii cron-скрипты (shel_youtube.sh, shel_youtube_time.sh).
# После миграции эти расписания переедут в новую таблицу dle_ingestion_schedules.
# Сейчас — Python-конфиг в коде, чтобы big-bang не требовал новой таблицы.

# Что было в shel_youtube.sh (02:00 nightly)
DLE_NIGHTLY_INGESTIONS: list[tuple[str, int, int, str]] = [
    # (source_slug, channel_id, limit, media_type)
    ("knigi_audio_biz",     6, 3, "video"),   # unique_audio/upload_to_youtube 3 6
    ("audiokniga_one_com",  5, 1, "video"),   # audiokniga_one_com/upload_to_youtube 1 5
    ("club_books_ru",       21, 1, "video"),
    ("books_online_info",   23, 1, "video"),
    ("bazaknig_net",        26, 2, "video"),
    ("bazaknig_net",        27, 3, "video"),
    ("bazaknig_net",        29, 3, "video"),
    ("bazaknig_net",        30, 3, "video"),
    ("bazaknig_net",        32, 3, "video"),
    ("bazaknig_net",        47, 3, "video"),
    ("bazaknig_net",        48, 3, "video"),
]

# Что было в shel_youtube_time.sh (14:15, 16:15, 21:15) — shorts
DLE_SHORTS_INGESTIONS: list[tuple[str, int, int]] = [
    # (source_slug, channel_id, limit)
    ("knigi_audio_biz",     6, 1),    # unique_audio/shorts 6
    ("audiokniga_one_com",  5, 1),
    ("club_books_ru",       21, 1),
    ("books_online_info",   23, 1),
    ("bazaknig_net",        26, 1),
    ("bazaknig_net",        27, 1),
    ("bazaknig_net",        29, 1),
    ("bazaknig_net",        30, 1),
    ("bazaknig_net",        32, 1),
    ("bazaknig_net",        33, 1),
    ("bazaknig_net",        47, 1),
    ("bazaknig_net",        48, 1),
]

# Что было в shel_youtube_time_2.sh (17:15, 20:15)
DLE_SHORTS_SLUSHAT: list[tuple[str, int, int]] = [
    ("slushat_knigi_com", 25, 1),
]

# Что было в shel_youtube_shorts_from_video.sh (13:20) — shorts из донорских YT-видео
SHORTS_FROM_VIDEO_CHANNELS: list[int] = [28]

# Sora AI feed → shorts (Yii: php yii sora/get_video --channel-id=N, manual)
# (channel_id, limit, media_type)
SORA_DAILY_CHANNELS: list[tuple[int, int, str]] = [
    (19, 3, "shorts"),
]


def enqueue_dle_nightly() -> int:
    """Запустить ночные DLE-ingestion (видео). Соответствует shel_youtube.sh@02:00."""
    count = 0
    for slug, channel_id, limit, media_type in DLE_NIGHTLY_INGESTIONS:
        try:
            enqueue_dle_ingestion(DleIngestionPayload(
                source_slug=slug,
                channel_id=channel_id,
                limit=limit,
                media_type=media_type,
            ))
            count += 1
        except Exception:
            logger.exception("DLE nightly enqueue failed: %s → %s", slug, channel_id)
    logger.info("DLE nightly: enqueued %d ingestions", count)
    return count


def enqueue_dle_shorts() -> int:
    """Запустить shorts-ingestion (короткие нарезки из аудиокниг). Соответствует shel_youtube_time.sh."""
    count = 0
    for slug, channel_id, limit in DLE_SHORTS_INGESTIONS:
        try:
            enqueue_dle_ingestion(DleIngestionPayload(
                source_slug=slug,
                channel_id=channel_id,
                limit=limit,
                media_type="shorts",
            ))
            count += 1
        except Exception:
            logger.exception("DLE shorts enqueue failed: %s → %s", slug, channel_id)
    logger.info("DLE shorts: enqueued %d ingestions", count)
    return count


def enqueue_slushat_shorts() -> int:
    """Запустить shorts только для slushat_knigi_com. Соответствует shel_youtube_time_2.sh."""
    count = 0
    for slug, channel_id, limit in DLE_SHORTS_SLUSHAT:
        try:
            enqueue_dle_ingestion(DleIngestionPayload(
                source_slug=slug,
                channel_id=channel_id,
                limit=limit,
                media_type="shorts",
            ))
            count += 1
        except Exception:
            logger.exception("Slushat shorts enqueue failed: %s → %s", slug, channel_id)
    logger.info("Slushat shorts: enqueued %d ingestions", count)
    return count


def enqueue_shorts_from_video() -> int:
    """Shorts из донорских YT-видео. Соответствует shel_youtube_shorts_from_video.sh@13:20."""
    count = 0
    for channel_id in SHORTS_FROM_VIDEO_CHANNELS:
        try:
            enqueue_shorts(ShortsPayload(channel_id=channel_id, limit=5))
            count += 1
        except Exception:
            logger.exception("Shorts from video enqueue failed: channel=%s", channel_id)
    logger.info("Shorts from video: enqueued %d", count)
    return count


def enqueue_sora_daily() -> int:
    """Запустить ежедневный Sora-скрейп. Соответствует Yii `sora/get_video --channel-id=N`.

    Раньше вызывалось вручную; теперь — раз в сутки (см. _YII_CRON @ 11:00).
    """
    count = 0
    for channel_id, limit, media_type in SORA_DAILY_CHANNELS:
        try:
            enqueue_sora(SoraPayload(
                channel_id=channel_id,
                limit=limit,
                media_type=media_type,
            ))
            count += 1
        except Exception:
            logger.exception("Sora daily enqueue failed: channel=%s", channel_id)
    logger.info("Sora daily: enqueued %d", count)
    return count


# ─── Cron-эмулятор для Yii pipelines (in-memory tracking) ────────────
#
# Каждый ключ → (hour, minute) когда срабатывает.
# scheduler/run.py вызывает run_periodic_yii_jobs() раз в минуту.
# После запуска job'а обновляется last_run_key чтобы не дублировать.

_yii_last_run: dict[str, str] = {}  # job_name → "YYYY-MM-DD HH:MM"

_YII_CRON: list[tuple[str, int, int, callable]] = [
    # (job_name, hour, minute, callable_returning_int)
    ("dle_nightly",        2, 0,  enqueue_dle_nightly),       # shel_youtube.sh
    ("dle_shorts_1",      14, 15, enqueue_dle_shorts),         # shel_youtube_time.sh
    ("dle_shorts_2",      16, 15, enqueue_dle_shorts),
    ("dle_shorts_3",      21, 15, enqueue_dle_shorts),
    ("slushat_shorts_1",  17, 15, enqueue_slushat_shorts),     # shel_youtube_time_2.sh
    ("slushat_shorts_2",  20, 15, enqueue_slushat_shorts),
    ("shorts_from_video", 13, 20, enqueue_shorts_from_video),  # shel_youtube_shorts_from_video.sh
    ("sora_daily",        11, 0,  enqueue_sora_daily),          # Yii sora/get_video, ранее вручную
]


def run_periodic_yii_jobs() -> int:
    """Проверяет cron-расписание и запускает соответствующие job'ы. Вызывается каждую минуту.

    Returns кол-во запущенных job'ов в этот вызов (обычно 0 или 1).
    """
    from datetime import datetime
    now = datetime.now()
    current_minute_key = now.strftime("%Y-%m-%d %H:%M")
    fired = 0
    for job_name, hh, mm, fn in _YII_CRON:
        if now.hour != hh or now.minute != mm:
            continue
        if _yii_last_run.get(job_name) == current_minute_key:
            continue  # Уже запускали в эту минуту
        try:
            count = fn()
            _yii_last_run[job_name] = current_minute_key
            logger.info("Yii cron fired: %s @ %02d:%02d → %d enqueued", job_name, hh, mm, count)
            fired += 1
        except Exception:
            logger.exception("Yii cron job failed: %s", job_name)
    return fired
