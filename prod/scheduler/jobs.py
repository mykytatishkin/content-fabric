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
    enqueue_dle_quotes_shorts,
    enqueue_news,
)
from shared.queue.types import (
    VideoUploadPayload,
    DleIngestionPayload,
    ShortsPayload,
    SoraPayload,
    VoiceChangePayload,
    DleQuotesShortsPayload,
    NewsPayload,
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
        # Still push (empty) gauge so dashboard knows the job ran.
        try:
            from shared.metrics import push_youtube_token_expiries
            push_youtube_token_expiries()
        except Exception:
            logger.exception("push_youtube_token_expiries failed")
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

    # Push fresh token-expiry gauges to pushgateway. Tokens were just refreshed
    # above (ensure_fresh_credentials updates token_expires_at in DB), so this
    # read sees current values and the Grafana panel sees real data.
    try:
        from shared.metrics import push_youtube_token_expiries
        reported = push_youtube_token_expiries()
        logger.info("Pushed cff_youtube_token_expires_in_seconds for %d channels", reported)
    except Exception:
        logger.exception("push_youtube_token_expiries failed")

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

# DLE quotes shorts: 1 quote per source per day → 1080×1920 vertical short.
# 1:1 port of all 7 Yii actionShorts. Each source has its own quotes.txt file
# in /var/www/.../data/{source-slug}/shorts/quotes.txt — that path is mounted
# read-write into CFF as DLE_QUOTES_BASE_DIR (defaults below).
import os as _os
DLE_QUOTES_BASE_DIR = _os.environ.get(
    "DLE_QUOTES_BASE_DIR",
    "/var/www/fastuser/data/www/aiyoutube.pbnbots.com/data",
)
# (source_slug, channel_id, language)
DLE_QUOTES_SHORTS_SOURCES: list[tuple[str, int, str]] = [
    ("audiokniga_one_com",  5,  "ru"),
    ("knigi_audio_biz",     6,  "ru"),
    ("club_books_ru",       21, "ru"),
    ("books_online_info",   23, "ru"),
    ("slushat_knigi_com",   25, "ru"),
    ("knigi_online_club",   12, "ru"),
    ("bazaknig_net",        26, "ru"),
]

# News pipeline: RBC RSS → long video (id_yt_acc=55 in Yii).
# Scheduled at 03:00 daily (after dle_nightly @ 02:00 finished).
NEWS_LONG_CHANNELS: list[tuple[int, str]] = [(55, "uk")]

# News shorts: vertical 1080×1920 with subtitle burn-in. shel_youtube_news.sh.
NEWS_SHORTS_CHANNELS: list[tuple[int, str]] = [(55, "uk")]

# Sora MEME mode (Yii classic actionShorts) — separate from SORA_DAILY_CHANNELS
# which uses the standard Whisper-highlights pipeline.
# (channel_id, limit)
SORA_MEME_CHANNELS: list[tuple[int, int]] = [
    (20, 3),
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


def enqueue_sora_meme_daily() -> int:
    """Sora pipeline в meme-mode (Yii classic actionShorts).

    GPT Vision frame descriptions → meme caption → JSON metadata →
    ffmpeg drawtext overlay. Insert directly to Tasks (skips Whisper).
    """
    count = 0
    for channel_id, limit in SORA_MEME_CHANNELS:
        try:
            enqueue_sora(SoraPayload(
                channel_id=channel_id,
                limit=limit,
                media_type="shorts",
                metadata={"mode": "meme"},
            ))
            count += 1
        except Exception:
            logger.exception("Sora meme enqueue failed: channel=%s", channel_id)
    logger.info("Sora meme: enqueued %d", count)
    return count


def enqueue_dle_quotes_shorts_daily() -> int:
    """1 quote per DLE source per day → 1080×1920 short.

    Replaces all 7 Yii actionShorts shel_youtube_time*.sh cron entries.
    Each source has its own quotes.txt; we pop one quote per call.
    """
    count = 0
    for source_slug, channel_id, language in DLE_QUOTES_SHORTS_SOURCES:
        # Yii path layout:
        #   data/{source-with-dots}/shorts/quotes.txt
        #   data/{source-with-dots}/shorts/backgrounds/
        #   data/{source-with-dots}/shorts/bg_music/
        # Source slugs use _ in CFF but . in Yii filesystem (audiokniga-one.com
        # vs audiokniga_one_com). We map back via a static dict.
        slug_to_dir = {
            "audiokniga_one_com": "audiokniga-one.com",
            "knigi_audio_biz":    "unique_audio",   # Yii: data/unique_audio
            "club_books_ru":      "club-books.ru",
            "books_online_info":  "books-online.info",
            "slushat_knigi_com":  "slushat-knigi.com",
            "knigi_online_club":  "knigi-online.club",
            "bazaknig_net":       "bazaknig.net",
        }
        dir_name = slug_to_dir.get(source_slug, source_slug)
        base = f"{DLE_QUOTES_BASE_DIR}/{dir_name}/shorts"
        quotes_file = f"{base}/quotes.txt"
        if source_slug == "knigi_audio_biz":
            # Yii: quotes_popadanci.txt — different file name for the unique_audio
            # / попаданцы flow.
            quotes_file = f"{base}/quotes_popadanci.txt"

        try:
            enqueue_dle_quotes_shorts(DleQuotesShortsPayload(
                source_slug=source_slug,
                channel_id=channel_id,
                quotes_file=quotes_file,
                backgrounds_dir=f"{base}/backgrounds",
                bg_music_dir=f"{base}/bg_music",
                language=language,
            ))
            count += 1
        except Exception:
            logger.exception("DLE quotes shorts enqueue failed: %s", source_slug)
    logger.info("DLE quotes shorts: enqueued %d sources", count)
    return count


def enqueue_news_long_daily() -> int:
    """RBC RSS → 5 SerpAPI photos + TTS + Ken Burns 1920×1080. Yii shel_youtube.sh."""
    count = 0
    for channel_id, language in NEWS_LONG_CHANNELS:
        try:
            enqueue_news(NewsPayload(
                channel_id=channel_id,
                media_type="video",
                language=language,
            ))
            count += 1
        except Exception:
            logger.exception("News long enqueue failed: channel=%s", channel_id)
    logger.info("News long: enqueued %d", count)
    return count


def enqueue_news_shorts_daily() -> int:
    """RBC RSS → vertical 1080×1920 + burn-in subtitles. Yii shel_youtube_news.sh."""
    count = 0
    for channel_id, language in NEWS_SHORTS_CHANNELS:
        try:
            enqueue_news(NewsPayload(
                channel_id=channel_id,
                media_type="shorts",
                language=language,
            ))
            count += 1
        except Exception:
            logger.exception("News shorts enqueue failed: channel=%s", channel_id)
    logger.info("News shorts: enqueued %d", count)
    return count


# ─── Cron-эмулятор для Yii pipelines (in-memory tracking) ────────────
#
# Каждый ключ → (hour, minute) когда срабатывает.
# scheduler/run.py вызывает run_periodic_yii_jobs() раз в минуту.
# После запуска job'а обновляется last_run_key чтобы не дублировать.

_yii_last_run: dict[str, str] = {}  # job_name → "YYYY-MM-DD HH:MM"

_YII_CRON: list[tuple[str, int, int, callable]] = [
    # (job_name, hour, minute, callable_returning_int)
    ("dle_nightly",         2, 0,  enqueue_dle_nightly),         # shel_youtube.sh
    ("news_long_daily",     3, 0,  enqueue_news_long_daily),     # RBC long video
    ("dle_quotes_shorts",   9, 0,  enqueue_dle_quotes_shorts_daily),  # all 7 sources
    ("sora_daily",         11, 0,  enqueue_sora_daily),           # standard mode
    ("sora_meme_daily",    11, 30, enqueue_sora_meme_daily),      # Yii classic mode
    ("news_shorts_daily",  11, 30, enqueue_news_shorts_daily),    # shel_youtube_news.sh
    ("shorts_from_video",  13, 20, enqueue_shorts_from_video),    # shel_youtube_shorts_from_video.sh
    ("dle_shorts_1",       14, 15, enqueue_dle_shorts),           # shel_youtube_time.sh
    ("dle_shorts_2",       16, 15, enqueue_dle_shorts),
    ("slushat_shorts_1",   17, 15, enqueue_slushat_shorts),       # shel_youtube_time_2.sh
    ("slushat_shorts_2",   20, 15, enqueue_slushat_shorts),
    ("dle_shorts_3",       21, 15, enqueue_dle_shorts),
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


# ── stream reconcile loop ────────────────────────────────────────────

# Per-stream throttle: don't poke a stream more than once every N seconds.
# YouTube's liveBroadcasts.transition is rate-limited and noisy reconciliations
# can also step on a healthy ffmpeg that's mid-handshake.
_RECONCILE_COOLDOWN_SEC = 300  # 5 min
_last_reconcile_at: dict[int, float] = {}


def reconcile_streams() -> tuple[int, int]:
    """Heal any enabled streams whose systemd unit isn't `active running`.

    Mirrors the periodic supervisor loop the PHP stack used to run as a cron.
    Returns ``(checked, healed)`` so the caller can log/expose metrics.

    Throttled per-stream by `_RECONCILE_COOLDOWN_SEC` so a flapping unit
    doesn't burn YouTube API quota.
    """
    import time as _time
    from sqlalchemy import text as _text

    from shared.db.connection import get_connection as _get_conn
    from shared.streams import lifecycle as _lifecycle

    sql = """
        SELECT id, name, service_name, workdir, stream_key, duration_sec,
               rtmp_host, rtmp_base, channel_id, streaming_account_id,
               platform_broadcast_id, platform_stream_id,
               title, description, tags, thumbnail_path, enabled
        FROM live_stream_configurations
        WHERE enabled = 1
        ORDER BY id ASC
    """
    try:
        with _get_conn() as conn:
            rows = conn.execute(_text(sql)).mappings().all()
    except Exception:
        logger.exception("[STREAM RECONCILE] failed to load streams")
        return (0, 0)

    now = _time.time()
    checked = 0
    healed = 0
    for r in rows:
        s = dict(r)
        sid = int(s["id"])
        last = _last_reconcile_at.get(sid, 0.0)
        if now - last < _RECONCILE_COOLDOWN_SEC:
            continue
        checked += 1
        try:
            res = _lifecycle.reconcile(s)
        except Exception:
            logger.exception("[STREAM RECONCILE] reconcile crashed for stream=%s", sid)
            continue
        _last_reconcile_at[sid] = now
        action = res.get("action")
        if action == "started":
            healed += 1
            logger.info(
                "[STREAM RECONCILE] healed stream=%s (%s) — broadcast=%s prep_err=%s live_err=%s",
                sid, res.get("reason"), res.get("broadcast_id"),
                res.get("prep_error"), res.get("live_error"),
            )
        else:
            logger.debug("[STREAM RECONCILE] noop stream=%s", sid)
    return (checked, healed)
