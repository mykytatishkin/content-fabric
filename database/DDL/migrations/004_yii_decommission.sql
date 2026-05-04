-- 004_yii_decommission.sql
-- Migration from Yii2 tables to CFF tables
-- VERIFIED against actual production schemas (2026-05-02)
--
-- Maps:
--   youtube_channels   -> platform_channels
--   google_consoles    -> platform_oauth_credentials
--   tasks              -> content_upload_queue_tasks
--   stream             -> live_stream_configurations
--   youtube_channel_daily -> channel_daily_statistics
--
-- All INSERT IGNORE to be idempotent (re-runnable).

-- ───────────────────────────────────────────────────────────────────
-- 1. google_consoles -> platform_oauth_credentials
-- ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO platform_oauth_credentials (
    project_id,
    platform,
    name,
    cloud_project_id,
    client_id,
    client_secret,
    redirect_uris,
    credentials_file,
    description,
    enabled,
    created_at,
    updated_at
)
SELECT
    1                                      AS project_id,
    'google'                               AS platform,
    name,
    project_id                             AS cloud_project_id,
    client_id,
    client_secret,
    redirect_uris,
    credentials_file,
    description,
    COALESCE(enabled, 1),
    COALESCE(created_at, NOW()),
    COALESCE(updated_at, NOW())
FROM google_consoles
WHERE NOT EXISTS (
    SELECT 1 FROM platform_oauth_credentials poc
    WHERE poc.name = google_consoles.name AND poc.platform = 'google'
);

-- ───────────────────────────────────────────────────────────────────
-- 2. youtube_channels -> platform_channels
--   Yii cols: id, name, channel_id (yt-id), console_id, access_token,
--             refresh_token, token_expires_at, enabled, add_info
-- ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO platform_channels (
    uuid,
    project_id,
    console_id,
    platform,
    name,
    platform_channel_id,
    access_token,
    refresh_token,
    token_expires_at,
    enabled,
    metadata,
    created_at,
    updated_at
)
SELECT
    UUID()                                                          AS uuid,
    1                                                               AS project_id,
    -- map old console_id (FK to google_consoles) to new oauth row
    (SELECT poc.id FROM platform_oauth_credentials poc
        JOIN google_consoles gc ON gc.name = poc.name
       WHERE gc.id = youtube_channels.console_id
       LIMIT 1)                                                     AS console_id,
    'youtube'                                                       AS platform,
    name,
    channel_id                                                      AS platform_channel_id,
    access_token,
    refresh_token,
    token_expires_at,
    COALESCE(enabled, 1)                                            AS enabled,
    CASE WHEN add_info IS NULL THEN NULL
         ELSE JSON_OBJECT('legacy_add_info', add_info) END          AS metadata,
    COALESCE(created_at, NOW()),
    COALESCE(updated_at, NOW())
FROM youtube_channels
WHERE NOT EXISTS (
    SELECT 1 FROM platform_channels pc
    WHERE pc.platform = 'youtube'
      AND pc.platform_channel_id = youtube_channels.channel_id
);

-- ───────────────────────────────────────────────────────────────────
-- 3. tasks -> content_upload_queue_tasks
--   Yii cols: id, account_id, media_type, status, date_add, att_file_path,
--             cover, title, description, keywords, post_comment,
--             add_info, date_post, date_done, upload_id, error_message
-- ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO content_upload_queue_tasks (
    uuid,
    project_id,
    channel_id,
    platform,
    media_type,
    status,
    source_file_path,
    thumbnail_path,
    title,
    description,
    keywords,
    post_comment,
    legacy_add_info,
    scheduled_at,
    completed_at,
    upload_id,
    error_message,
    retry_count,
    max_retries,
    created_at,
    updated_at
)
SELECT
    UUID()                                                          AS uuid,
    1                                                               AS project_id,
    -- map old account_id (Yii youtube_channels.id) to new platform_channels.id
    (SELECT pc.id FROM platform_channels pc
        JOIN youtube_channels yc ON yc.channel_id = pc.platform_channel_id
                                  AND pc.platform = 'youtube'
       WHERE yc.id = tasks.account_id
       LIMIT 1)                                                     AS channel_id,
    'youtube'                                                       AS platform,
    CASE WHEN media_type = 'shorts' THEN 'shorts'
         WHEN media_type = 'live'   THEN 'stream'
         ELSE 'video' END                                           AS media_type,
    COALESCE(status, 0)                                             AS status,
    att_file_path                                                   AS source_file_path,
    cover                                                           AS thumbnail_path,
    COALESCE(title, '')                                             AS title,
    description,
    keywords,
    post_comment,
    add_info                                                        AS legacy_add_info,
    COALESCE(date_post, COALESCE(date_add, NOW()))                  AS scheduled_at,
    date_done                                                       AS completed_at,
    upload_id,
    error_message,
    0                                                               AS retry_count,
    3                                                               AS max_retries,
    COALESCE(date_add, NOW())                                       AS created_at,
    COALESCE(date_add, NOW())                                       AS updated_at
FROM tasks
WHERE tasks.account_id IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM platform_channels pc
        JOIN youtube_channels yc ON yc.channel_id = pc.platform_channel_id
                                  AND pc.platform = 'youtube'
       WHERE yc.id = tasks.account_id
  );

-- ───────────────────────────────────────────────────────────────────
-- 4. stream -> live_stream_configurations
--   Yii cols: id, name, service_name, workdir, runner_path, channel_name,
--             enabled, notes, created_at, updated_at, stream_key,
--             duration_sec, rtmp_base, rtmp_host,
--             youtube_broadcast_id, youtube_video_id,
--             yt_title, yt_description, yt_tags, yt_thumbnail,
--             youtube_account_id (FK to youtube_account, NOT youtube_channels!),
--             youtube_stream_id, youtube_stream_key
-- ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO live_stream_configurations (
    project_id,
    streaming_account_id,
    channel_id,
    name,
    service_name,
    workdir,
    rtmp_host,
    rtmp_base,
    stream_key,
    duration_sec,
    platform_broadcast_id,
    platform_video_id,
    platform_stream_id,
    platform_stream_key,
    title,
    description,
    tags,
    thumbnail_path,
    enabled,
    notes,
    created_at,
    updated_at
)
SELECT
    1                                                               AS project_id,
    youtube_account_id                                              AS streaming_account_id,
    -- best-effort map: streams.channel_name → platform_channels.name (may be NULL)
    (SELECT pc.id FROM platform_channels pc
       WHERE pc.platform = 'youtube'
         AND pc.name = stream.channel_name
       LIMIT 1)                                                     AS channel_id,
    name,
    service_name,
    workdir,
    rtmp_host,
    rtmp_base,
    stream_key,
    COALESCE(duration_sec, 42900)                                   AS duration_sec,
    youtube_broadcast_id                                            AS platform_broadcast_id,
    youtube_video_id                                                AS platform_video_id,
    youtube_stream_id                                               AS platform_stream_id,
    youtube_stream_key                                              AS platform_stream_key,
    yt_title                                                        AS title,
    yt_description                                                  AS description,
    yt_tags                                                         AS tags,
    yt_thumbnail                                                    AS thumbnail_path,
    COALESCE(enabled, 1),
    notes,
    -- created_at/updated_at в Yii — int unix timestamp; конвертим
    FROM_UNIXTIME(COALESCE(created_at, UNIX_TIMESTAMP())),
    FROM_UNIXTIME(COALESCE(updated_at, UNIX_TIMESTAMP()))
FROM stream
WHERE NOT EXISTS (
    SELECT 1 FROM live_stream_configurations lsc
    WHERE lsc.service_name = stream.service_name
);

-- ───────────────────────────────────────────────────────────────────
-- 5. youtube_channel_daily -> channel_daily_statistics
--   Yii cols: id, yt_channel_id (legacy local FK), channel_id (yt id varchar),
--             snapshot_date, subscribers, views, videos, created_at
-- ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO channel_daily_statistics (
    channel_id,
    platform_channel_id,
    snapshot_date,
    subscribers,
    views,
    videos,
    created_at
)
SELECT
    (SELECT pc.id FROM platform_channels pc
       WHERE pc.platform = 'youtube'
         AND pc.platform_channel_id = youtube_channel_daily.channel_id
       LIMIT 1)                                                     AS channel_id,
    youtube_channel_daily.channel_id                                AS platform_channel_id,
    snapshot_date,
    subscribers,
    views,
    videos,
    COALESCE(created_at, NOW())
FROM youtube_channel_daily
WHERE EXISTS (
    SELECT 1 FROM platform_channels pc
    WHERE pc.platform = 'youtube'
      AND pc.platform_channel_id = youtube_channel_daily.channel_id
);

-- ───────────────────────────────────────────────────────────────────
-- 6. Записать миграцию
-- ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO platform_schema_migrations (version, applied_at)
VALUES ('004_yii_decommission', NOW());

-- ВНИМАНИЕ: drop старых таблиц — отдельно в 005_drop_yii_tables.sql
--           запускается ТОЛЬКО после verify через scripts/compare_yii_cff_data.py
