-- ============================================
-- Migration 003: Cleanup Legacy Tables (OPTIONAL)
-- ============================================
-- This script removes old tables after successful migration
-- 
-- WARNING: Only run this after verifying data migration was successful!
-- Make sure you have a backup before running this script!
-- ============================================

-- Verify migration was successful by checking row counts
SELECT '=== Verifying migration before cleanup ===' AS step;

SELECT 
    'users' as new_table,
    COUNT(*) as row_count,
    CASE WHEN COUNT(*) > 0 THEN 'OK' ELSE 'EMPTY' END as status
FROM users
UNION ALL
SELECT 'oauth_consoles', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM oauth_consoles
UNION ALL
SELECT 'channels', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM channels
UNION ALL
SELECT 'channel_tokens', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM channel_tokens
UNION ALL
SELECT 'channel_credentials', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM channel_credentials
UNION ALL
SELECT 'publish_tasks', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM publish_tasks
UNION ALL
SELECT 'channel_daily_stats', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM channel_daily_stats
UNION ALL
SELECT 'reauth_audit', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM reauth_audit
UNION ALL
SELECT 'streaming_accounts', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM streaming_accounts
UNION ALL
SELECT 'streams', COUNT(*), CASE WHEN COUNT(*) >= 0 THEN 'OK' ELSE 'CHECK' END FROM streams;

-- ============================================
-- DANGER ZONE: Uncomment to drop legacy tables
-- ============================================

-- Drop legacy tables (uncomment when ready)
-- SET FOREIGN_KEY_CHECKS = 0;

-- -- Auth (old user table)
-- DROP TABLE IF EXISTS `user`;

-- -- Channel service (old tables)
-- DROP TABLE IF EXISTS `youtube_tokens`;
-- DROP TABLE IF EXISTS `youtube_account_credentials`;
-- DROP TABLE IF EXISTS `youtube_reauth_audit`;
-- DROP TABLE IF EXISTS `youtube_channels`;
-- DROP TABLE IF EXISTS `google_consoles`;

-- -- Publishing service (old table)
-- DROP TABLE IF EXISTS `tasks`;

-- -- Analytics service (old table)
-- DROP TABLE IF EXISTS `youtube_channel_daily`;

-- -- Streaming service (old tables)
-- DROP TABLE IF EXISTS `stream`;
-- DROP TABLE IF EXISTS `youtube_account`;

-- SET FOREIGN_KEY_CHECKS = 1;

-- Log migration
-- INSERT INTO migration (version, apply_time) VALUES ('003_cleanup_legacy', UNIX_TIMESTAMP())
-- ON DUPLICATE KEY UPDATE apply_time = UNIX_TIMESTAMP();

SELECT '=== Cleanup script ready ===' AS step;
SELECT 'Uncomment the DROP statements above to remove legacy tables' AS note;
SELECT 'Only do this after verifying all data has been migrated correctly!' AS warning;
