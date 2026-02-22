-- ============================================================================
-- Rollback 002: Remove migrated identity data
-- Reverses: 002_migrate_identity.sql
-- Keeps table structure, removes only migrated data
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM `platform_project_members`;
DELETE FROM `platform_projects`;
DELETE FROM `platform_users`;

DELETE FROM `platform_schema_migrations` WHERE `version` = '002_migrate_identity';

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Rollback 002 complete: identity data cleared.' AS result;
