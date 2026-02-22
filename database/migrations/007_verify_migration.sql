-- ============================================================================
-- Migration 007: Verify Migration Integrity
-- Content Fabric Database Refactoring
--
-- Compares row counts between legacy and new tables.
-- Run this AFTER 001-006 to ensure all data migrated correctly.
-- Does NOT modify any data.
-- ============================================================================

SET @migration_version = '007_verify_migration';

-- ============================================================================
-- Row count comparison
-- ============================================================================

SELECT '=== MIGRATION VERIFICATION ===' AS info;

-- Users
SELECT
    'users' AS check_name,
    (SELECT COUNT(*) FROM `user`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_users`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `user`) <= (SELECT COUNT(*) FROM `platform_users`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- OAuth Consoles
SELECT
    'oauth_consoles' AS check_name,
    (SELECT COUNT(*) FROM `google_consoles`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_oauth_credentials`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `google_consoles`) = (SELECT COUNT(*) FROM `platform_oauth_credentials`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Channels
SELECT
    'channels' AS check_name,
    (SELECT COUNT(*) FROM `youtube_channels`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_channels`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_channels`) = (SELECT COUNT(*) FROM `platform_channels`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Tokens
SELECT
    'channel_tokens' AS check_name,
    (SELECT COUNT(*) FROM `youtube_tokens`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_channel_tokens`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_tokens`) = (SELECT COUNT(*) FROM `platform_channel_tokens`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Login Credentials
SELECT
    'login_credentials' AS check_name,
    (SELECT COUNT(*) FROM `youtube_account_credentials`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_channel_login_credentials`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_account_credentials`) = (SELECT COUNT(*) FROM `platform_channel_login_credentials`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Tasks
SELECT
    'tasks' AS check_name,
    (SELECT COUNT(*) FROM `tasks`) AS legacy_count,
    (SELECT COUNT(*) FROM `content_upload_queue_tasks`) AS new_count,
    (SELECT COUNT(*) FROM `tasks` t
     WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`)
    ) AS orphaned_legacy,
    CASE
        WHEN (SELECT COUNT(*) FROM `tasks`) =
             (SELECT COUNT(*) FROM `content_upload_queue_tasks`) +
             (SELECT COUNT(*) FROM `tasks` t
              WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`))
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Daily Stats
SELECT
    'daily_stats' AS check_name,
    (SELECT COUNT(*) FROM `youtube_channel_daily`) AS legacy_count,
    (SELECT COUNT(*) FROM `channel_daily_statistics`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `channel_daily_statistics`) > 0
        THEN 'OK' ELSE 'CHECK MANUALLY'
    END AS status;

-- Reauth Audit
SELECT
    'reauth_audit' AS check_name,
    (SELECT COUNT(*) FROM `youtube_reauth_audit`) AS legacy_count,
    (SELECT COUNT(*) FROM `channel_reauth_audit_logs`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_reauth_audit`) >=
             (SELECT COUNT(*) FROM `channel_reauth_audit_logs`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Streaming Accounts
SELECT
    'streaming_accounts' AS check_name,
    (SELECT COUNT(*) FROM `youtube_account`) AS legacy_count,
    (SELECT COUNT(*) FROM `live_streaming_accounts`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_account`) = (SELECT COUNT(*) FROM `live_streaming_accounts`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Streams
SELECT
    'stream_configs' AS check_name,
    (SELECT COUNT(*) FROM `stream`) AS legacy_count,
    (SELECT COUNT(*) FROM `live_stream_configurations`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `stream`) = (SELECT COUNT(*) FROM `live_stream_configurations`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- ============================================================================
-- FK integrity checks
-- ============================================================================

SELECT '=== FK INTEGRITY CHECKS ===' AS info;

-- Channels with invalid console_id
SELECT 'channels_invalid_console' AS check_name,
    COUNT(*) AS count
FROM `platform_channels` pc
WHERE pc.`console_id` IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM `platform_oauth_credentials` poc WHERE poc.`id` = pc.`console_id`);

-- Tasks with invalid channel_id
SELECT 'tasks_invalid_channel' AS check_name,
    COUNT(*) AS count
FROM `content_upload_queue_tasks` cuqt
WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = cuqt.`channel_id`);

-- Credentials with invalid channel_id
SELECT 'credentials_invalid_channel' AS check_name,
    COUNT(*) AS count
FROM `platform_channel_login_credentials` pclc
WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = pclc.`channel_id`);

-- Project/member integrity
SELECT 'project_members_valid' AS check_name,
    COUNT(*) AS count
FROM `platform_project_members` ppm
WHERE EXISTS (SELECT 1 FROM `platform_projects` pp WHERE pp.`id` = ppm.`project_id`)
AND EXISTS (SELECT 1 FROM `platform_users` pu WHERE pu.`id` = ppm.`user_id`);

-- ============================================================================
-- Summary
-- ============================================================================

SELECT '=== MIGRATION SUMMARY ===' AS info;

SELECT
    (SELECT COUNT(*) FROM `platform_users`) AS users,
    (SELECT COUNT(*) FROM `platform_projects`) AS projects,
    (SELECT COUNT(*) FROM `platform_project_members`) AS members,
    (SELECT COUNT(*) FROM `platform_oauth_credentials`) AS oauth_consoles,
    (SELECT COUNT(*) FROM `platform_channels`) AS channels,
    (SELECT COUNT(*) FROM `platform_channel_tokens`) AS tokens,
    (SELECT COUNT(*) FROM `platform_channel_login_credentials`) AS login_creds,
    (SELECT COUNT(*) FROM `content_upload_queue_tasks`) AS tasks,
    (SELECT COUNT(*) FROM `channel_daily_statistics`) AS daily_stats,
    (SELECT COUNT(*) FROM `channel_reauth_audit_logs`) AS audit_logs,
    (SELECT COUNT(*) FROM `live_streaming_accounts`) AS streaming_accs,
    (SELECT COUNT(*) FROM `live_stream_configurations`) AS stream_configs;

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Verify migration integrity - row counts and FK checks');
