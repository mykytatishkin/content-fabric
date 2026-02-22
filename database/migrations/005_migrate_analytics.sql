-- ============================================================================
-- Migration 005: Migrate Analytics & Audit
-- Content Fabric Database Refactoring
--
-- Migrates:
--   youtube_channel_daily  -> channel_daily_statistics (~2050 records)
--   youtube_reauth_audit   -> channel_reauth_audit_logs (~3550 records)
--
-- Key transformations:
--   - channel_name (string FK) -> channel_id (int FK)
--   - yt_channel_id -> proper FK via platform_channel_id lookup
--   - Added: trigger_reason, error_code, likes, comments, metadata
-- ============================================================================

SET @migration_version = '005_migrate_analytics';

-- ============================================================================
-- Step 1: youtube_channel_daily -> channel_daily_statistics
-- Legacy has yt_channel_id (int, no FK) + channel_id (string, YouTube ID)
-- New uses channel_id (int FK) + platform_channel_id (string)
-- ============================================================================

INSERT INTO `channel_daily_statistics` (
    `id`, `channel_id`, `platform_channel_id`, `snapshot_date`,
    `subscribers`, `views`, `videos`, `created_at`
)
SELECT
    ycd.`id`,
    pc.`id`,
    ycd.`channel_id`,          -- This is the YouTube channel string ID (UC...)
    ycd.`snapshot_date`,
    ycd.`subscribers`,
    ycd.`views`,
    ycd.`videos`,
    ycd.`created_at`
FROM `youtube_channel_daily` ycd
-- Join by platform_channel_id (the YouTube UC... string)
INNER JOIN `platform_channels` pc
    ON pc.`platform_channel_id` = ycd.`channel_id`
    AND pc.`platform` = 'youtube'
WHERE NOT EXISTS (
    SELECT 1 FROM `channel_daily_statistics` cds WHERE cds.`id` = ycd.`id`
);

-- Also migrate records where channel_id doesn't match but yt_channel_id does
-- (yt_channel_id is the integer ID referencing youtube_channels.id)
INSERT IGNORE INTO `channel_daily_statistics` (
    `channel_id`, `platform_channel_id`, `snapshot_date`,
    `subscribers`, `views`, `videos`, `created_at`
)
SELECT
    pc.`id`,
    ycd.`channel_id`,
    ycd.`snapshot_date`,
    ycd.`subscribers`,
    ycd.`views`,
    ycd.`videos`,
    ycd.`created_at`
FROM `youtube_channel_daily` ycd
INNER JOIN `platform_channels` pc ON pc.`id` = ycd.`yt_channel_id`
WHERE NOT EXISTS (
    SELECT 1 FROM `channel_daily_statistics` cds
    WHERE cds.`channel_id` = pc.`id` AND cds.`snapshot_date` = ycd.`snapshot_date`
)
AND ycd.`yt_channel_id` IS NOT NULL;

-- ============================================================================
-- Step 2: youtube_reauth_audit -> channel_reauth_audit_logs
-- Legacy uses channel_name (string FK) -> resolve to channel_id (int FK)
-- Added: trigger_reason, error_code (new fields, NULL for migrated data)
-- ============================================================================

INSERT INTO `channel_reauth_audit_logs` (
    `id`, `channel_id`, `initiated_at`, `completed_at`,
    `status`, `error_message`, `metadata`, `created_at`
)
SELECT
    yra.`id`,
    pc.`id`,
    yra.`initiated_at`,
    yra.`completed_at`,
    yra.`status`,
    yra.`error_message`,
    yra.`metadata`,
    COALESCE(yra.`initiated_at`, NOW())
FROM `youtube_reauth_audit` yra
INNER JOIN `platform_channels` pc ON pc.`name` = yra.`channel_name` AND pc.`platform` = 'youtube'
WHERE NOT EXISTS (
    SELECT 1 FROM `channel_reauth_audit_logs` cral WHERE cral.`id` = yra.`id`
);

-- Log orphaned audit records (channel doesn't exist)
SELECT COUNT(*) AS orphaned_reauth_audit_count
FROM `youtube_reauth_audit` yra
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channels` pc
    WHERE pc.`name` = yra.`channel_name` AND pc.`platform` = 'youtube'
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate youtube_channel_daily and youtube_reauth_audit to new analytics tables');
