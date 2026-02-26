-- ============================================================================
-- Rollback 004: Remove migrated publishing data
-- Reverses: 004_migrate_publishing.sql
-- ============================================================================

DELETE FROM `content_upload_queue_tasks`;

DELETE FROM `platform_schema_migrations` WHERE `version` = '004_migrate_publishing';

SELECT 'Rollback 004 complete: publishing tasks cleared.' AS result;
