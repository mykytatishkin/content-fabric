-- ============================================================================
-- Migration 006: Migrate Streaming
-- Content Fabric Database Refactoring
--
-- Migrates:
--   youtube_account -> live_streaming_accounts (~7 records)
--   stream          -> live_stream_configurations (~8 records)
--
-- Key transformations:
--   - token_expires (unix int) -> token_expires_at (TIMESTAMP)
--   - created_at/updated_at (unix int) -> TIMESTAMP
--   - youtube_* columns -> platform_* (platform-agnostic)
--   - yt_title/yt_description/etc -> title/description/etc
--   - All records assigned to @default_project_id
-- ============================================================================

SET @migration_version = '006_migrate_streaming';

SET @default_project_id = (SELECT `id` FROM `platform_projects` WHERE `slug` = 'default' LIMIT 1);

-- ============================================================================
-- Step 1: youtube_account -> live_streaming_accounts
-- ============================================================================

INSERT INTO `live_streaming_accounts` (
    `id`, `project_id`, `platform`, `name`,
    `client_id`, `client_secret`,
    `access_token`, `refresh_token`, `token_expires_at`,
    `enabled`, `created_at`, `updated_at`
)
SELECT
    ya.`id`,
    @default_project_id,
    'youtube',
    ya.`name`,
    ya.`client_id`,
    ya.`client_secret`,
    ya.`access_token`,
    ya.`refresh_token`,
    CASE
        WHEN ya.`token_expires` IS NOT NULL AND ya.`token_expires` > 0
        THEN FROM_UNIXTIME(ya.`token_expires`)
        ELSE NULL
    END,
    1,
    ya.`created_at`,
    ya.`updated_at`
FROM `youtube_account` ya
WHERE NOT EXISTS (
    SELECT 1 FROM `live_streaming_accounts` lsa WHERE lsa.`id` = ya.`id`
);

-- ============================================================================
-- Step 2: stream -> live_stream_configurations
-- Legacy created_at/updated_at are unix timestamps (INT)
-- youtube_* prefixed columns -> platform_* (platform-agnostic naming)
-- ============================================================================

INSERT INTO `live_stream_configurations` (
    `id`, `project_id`, `streaming_account_id`, `channel_id`,
    `name`, `service_name`, `workdir`,
    `rtmp_host`, `rtmp_base`, `stream_key`, `duration_sec`,
    `platform_broadcast_id`, `platform_video_id`,
    `platform_stream_id`, `platform_stream_key`,
    `title`, `description`, `tags`, `thumbnail_path`,
    `enabled`, `notes`,
    `created_at`, `updated_at`
)
SELECT
    s.`id`,
    @default_project_id,
    s.`youtube_account_id`,
    -- Resolve channel_name to channel_id (COLLATE needed: stream uses 0900_ai_ci)
    (SELECT pc.`id` FROM `platform_channels` pc
     WHERE pc.`name` = s.`channel_name` COLLATE utf8mb4_unicode_ci AND pc.`platform` = 'youtube' LIMIT 1),
    s.`name`,
    s.`service_name`,
    s.`workdir`,
    s.`rtmp_host`,
    s.`rtmp_base`,
    s.`stream_key`,
    COALESCE(s.`duration_sec`, 42900),
    s.`youtube_broadcast_id`,       -- -> platform_broadcast_id
    s.`youtube_video_id`,           -- -> platform_video_id
    s.`youtube_stream_id`,          -- -> platform_stream_id
    s.`youtube_stream_key`,         -- -> platform_stream_key
    s.`yt_title`,                   -- -> title
    s.`yt_description`,             -- -> description
    s.`yt_tags`,                    -- -> tags
    s.`yt_thumbnail`,               -- -> thumbnail_path
    COALESCE(s.`enabled`, 1),
    s.`notes`,
    CASE
        WHEN s.`created_at` > 1000000000
        THEN FROM_UNIXTIME(s.`created_at`)
        ELSE NOW()
    END,
    CASE
        WHEN s.`updated_at` > 1000000000
        THEN FROM_UNIXTIME(s.`updated_at`)
        ELSE NOW()
    END
FROM `stream` s
WHERE NOT EXISTS (
    SELECT 1 FROM `live_stream_configurations` lsc WHERE lsc.`id` = s.`id`
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate youtube_account and stream to new streaming tables');
