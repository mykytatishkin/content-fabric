-- ============================================
-- Rollback for Migration 002: Remove Migrated Data
-- ============================================
-- Use this if you need to re-run the data migration
-- This clears new tables but keeps the schema
-- ============================================

SET FOREIGN_KEY_CHECKS = 0;

-- Clear data from new tables (in reverse dependency order)
TRUNCATE TABLE streams;
TRUNCATE TABLE streaming_accounts;
TRUNCATE TABLE reauth_audit;
TRUNCATE TABLE channel_daily_stats;
TRUNCATE TABLE publish_tasks;
TRUNCATE TABLE channel_credentials;
TRUNCATE TABLE channel_tokens;
TRUNCATE TABLE channels;
TRUNCATE TABLE oauth_consoles;
-- Don't truncate users if you have real user data
-- TRUNCATE TABLE users;

SET FOREIGN_KEY_CHECKS = 1;

-- Remove migration record
DELETE FROM migration WHERE version = '002_migrate_data';

SELECT 'Rollback 002: Data cleared, ready for re-migration' AS status;
