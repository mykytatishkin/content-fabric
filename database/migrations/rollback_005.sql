-- ============================================================================
-- Rollback 005: Remove migrated analytics data
-- Reverses: 005_migrate_analytics.sql
-- ============================================================================

DELETE FROM `channel_reauth_audit_logs`;
DELETE FROM `channel_daily_statistics`;

DELETE FROM `platform_schema_migrations` WHERE `version` = '005_migrate_analytics';

SELECT 'Rollback 005 complete: analytics data cleared.' AS result;
