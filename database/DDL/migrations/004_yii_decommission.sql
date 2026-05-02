-- 004_yii_decommission.sql
-- Migration from Yii2 tables to CFF tables

-- 1. Channels mapping (youtube_channels -> platform_channels)
INSERT IGNORE INTO platform_channels (
    id, platform_id, platform_channel_id, name, custom_url, 
    thumbnails, is_enabled, console_id, access_token, 
    refresh_token, token_expires_at, last_token_check_at, 
    is_token_valid, created_at, updated_at
)
SELECT 
    id, 1, channel_id, name, custom_url,
    '{}', 1, google_console_id, access_token,
    refresh_token, token_expires_at, last_token_check,
    is_token_valid, created_at, updated_at
FROM youtube_channels;

-- 2. Tasks mapping (tasks -> content_upload_queue_tasks)
INSERT IGNORE INTO content_upload_queue_tasks (
    id, project_id, channel_id, media_type, status, 
    source_file_path, thumbnail_path, title, description, 
    keywords, post_comment, legacy_add_info, scheduled_at, 
    created_at, completed_at, upload_id, error_message, retry_count
)
SELECT 
    id, 1, account_id, IF(media_type='shorts', 'shorts', 'video'), status,
    att_file_path, cover, title, description,
    keywords, post_comment, NULL, date_post,
    date_add, IF(status=1, NOW(), NULL), NULL, NULL, 0
FROM tasks;

-- 3. Streams mapping (stream -> live_stream_configurations)
INSERT IGNORE INTO live_stream_configurations (
    id, channel_id, stream_key, stream_url, 
    is_active, last_start_at, last_stop_at, 
    created_at, updated_at
)
SELECT 
    id, id_yt_acc, stream_key, 'rtmp://a.rtmp.youtube.com/live2',
    1, NOW(), NULL,
    NOW(), NOW()
FROM stream;

-- 4. Stats mapping (youtube_channel_daily -> channel_daily_statistics)
INSERT IGNORE INTO channel_daily_statistics (
    channel_id, subscribers, views, videos, recorded_at
)
SELECT 
    id_yt_acc, subscribers, views, videos, date
FROM youtube_channel_daily;

-- Record migration
INSERT INTO platform_schema_migrations (version, applied_at) 
VALUES ('004_yii_decommission', NOW());
