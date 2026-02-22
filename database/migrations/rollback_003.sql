-- ============================================================================
-- Rollback 003: Remove migrated channel data
-- Reverses: 003_migrate_channels.sql
-- Keeps table structure, removes only migrated data
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM `platform_channel_login_credentials`;
DELETE FROM `platform_channel_tokens`;
DELETE FROM `platform_channels`;
DELETE FROM `platform_oauth_credentials`;

DELETE FROM `platform_schema_migrations` WHERE `version` = '003_migrate_channels';

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Rollback 003 complete: channel data cleared.' AS result;
