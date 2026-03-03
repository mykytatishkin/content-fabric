-- ============================================
-- Rollback for Migration 001: Drop New Schema
-- ============================================
-- Use this to completely remove the new schema
-- WARNING: This will delete all migrated data!
-- ============================================

SET FOREIGN_KEY_CHECKS = 0;

-- Drop new tables (in reverse dependency order)
DROP TABLE IF EXISTS streams;
DROP TABLE IF EXISTS streaming_accounts;
DROP TABLE IF EXISTS reauth_audit;
DROP TABLE IF EXISTS channel_daily_stats;
DROP TABLE IF EXISTS publish_tasks;
DROP TABLE IF EXISTS channel_credentials;
DROP TABLE IF EXISTS channel_tokens;
DROP TABLE IF EXISTS channels;
DROP TABLE IF EXISTS oauth_consoles;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- Remove migration records
DELETE FROM migration WHERE version IN ('001_create_schema', '002_migrate_data', '003_cleanup_legacy');

SELECT 'Rollback 001: New schema dropped, legacy tables remain intact' AS status;
