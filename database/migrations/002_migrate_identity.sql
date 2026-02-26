-- ============================================================================
-- Migration 002: Migrate Identity (Users, Projects, Members)
-- Content Fabric Database Refactoring
--
-- Migrates: user -> platform_users
-- Creates: default project + owner membership
-- ============================================================================

SET @migration_version = '002_migrate_identity';

-- ============================================================================
-- Step 1: Migrate users from legacy `user` table
-- Legacy uses unix INT timestamps, new uses TIMESTAMP
-- ============================================================================

INSERT INTO `platform_users` (
    `id`, `uuid`, `username`, `email`, `password_hash`, `auth_key`,
    `password_reset_token`, `verification_token`, `status`,
    `created_at`, `updated_at`
)
SELECT
    u.`id`,
    UUID(),
    u.`username`,
    u.`email`,
    u.`password_hash`,
    u.`auth_key`,
    u.`password_reset_token`,
    u.`verification_token`,
    u.`status`,
    FROM_UNIXTIME(u.`created_at`),
    FROM_UNIXTIME(u.`updated_at`)
FROM `user` u
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_users` pu WHERE pu.`id` = u.`id`
);

-- If no legacy users exist, create a default admin
INSERT INTO `platform_users` (`uuid`, `username`, `email`, `password_hash`, `auth_key`, `status`)
SELECT UUID(), 'admin', 'admin@content-fabric.local', NULL, LEFT(UUID(), 32), 10
FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM `platform_users`);

-- ============================================================================
-- Step 2: Create default project for the first user
-- All legacy data will be assigned to this project
-- ============================================================================

SET @default_user_id = (SELECT MIN(`id`) FROM `platform_users`);

INSERT INTO `platform_projects` (
    `uuid`, `owner_id`, `name`, `slug`, `description`,
    `subscription_plan`, `status`
)
SELECT
    UUID(),
    @default_user_id,
    'Default Project',
    'default',
    'Auto-created during migration from legacy schema. All existing resources assigned here.',
    'enterprise',
    10
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_projects` WHERE `slug` = 'default'
);

SET @default_project_id = (SELECT `id` FROM `platform_projects` WHERE `slug` = 'default' LIMIT 1);

-- ============================================================================
-- Step 3: Create owner membership for default user in default project
-- ============================================================================

INSERT INTO `platform_project_members` (
    `project_id`, `user_id`, `role`, `status`, `accepted_at`
)
SELECT
    @default_project_id,
    @default_user_id,
    'owner',
    'active',
    NOW()
FROM DUAL
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_project_members`
    WHERE `project_id` = @default_project_id AND `user_id` = @default_user_id
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate users from legacy, create default project and owner membership');
