-- ============================================================================
-- Migration 008: Cleanup Legacy Tables
-- Content Fabric Database Refactoring
--
-- !!! DANGER ZONE !!!
-- This script DROPS all legacy tables permanently.
-- Only run AFTER:
--   1. 007_verify_migration.sql shows all OK
--   2. Application code fully updated to use new tables
--   3. Production backup taken
--   4. Tested in staging environment
--
-- This migration is IRREVERSIBLE. No rollback possible.
-- ============================================================================

SET @migration_version = '008_cleanup_legacy';

-- ============================================================================
-- Safety check: ensure new tables have data
-- ============================================================================

SELECT
    'PRE-CLEANUP CHECK' AS info,
    (SELECT COUNT(*) FROM `platform_users`) AS new_users,
    (SELECT COUNT(*) FROM `platform_channels`) AS new_channels,
    (SELECT COUNT(*) FROM `content_upload_queue_tasks`) AS new_tasks;

-- UNCOMMENT THE LINES BELOW ONLY WHEN YOU ARE READY TO DROP LEGACY TABLES
-- Verify the counts above match expectations before proceeding.

-- ============================================================================
-- Drop legacy tables (in FK dependency order)
-- ============================================================================

/*
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `youtube_tokens`;
DROP TABLE IF EXISTS `youtube_account_credentials`;
DROP TABLE IF EXISTS `youtube_reauth_audit`;
DROP TABLE IF EXISTS `youtube_channel_daily`;
DROP TABLE IF EXISTS `tasks`;
DROP TABLE IF EXISTS `youtube_channels`;
DROP TABLE IF EXISTS `google_consoles`;
DROP TABLE IF EXISTS `stream`;
DROP TABLE IF EXISTS `youtube_account`;
DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS `migration`;

SET FOREIGN_KEY_CHECKS = 1;

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Dropped all legacy tables after successful migration');
*/

SELECT 'Legacy cleanup script loaded but NOT executed. Uncomment DROP statements when ready.' AS warning;
