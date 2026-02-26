-- ============================================================================
-- Rollback 006: Remove migrated streaming data
-- Reverses: 006_migrate_streaming.sql
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM `live_stream_configurations`;
DELETE FROM `live_streaming_accounts`;

DELETE FROM `platform_schema_migrations` WHERE `version` = '006_migrate_streaming';

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Rollback 006 complete: streaming data cleared.' AS result;
