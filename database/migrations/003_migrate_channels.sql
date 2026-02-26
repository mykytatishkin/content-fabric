-- ============================================================================
-- Migration 003: Migrate Channels & OAuth
-- Content Fabric Database Refactoring
--
-- Migrates:
--   google_consoles          -> platform_oauth_credentials
--   youtube_channels         -> platform_channels
--   youtube_tokens           -> platform_channel_tokens
--   youtube_account_credentials -> platform_channel_login_credentials
--
-- Key transformations:
--   - String FKs (channel_name) -> integer FKs (channel_id)
--   - channel_id column -> platform_channel_id (avoids PK confusion)
--   - console_name stored in metadata JSON for legacy compat
--   - All records assigned to @default_project_id
-- ============================================================================

SET @migration_version = '003_migrate_channels';

-- Get default project (created in 002)
SET @default_project_id = (SELECT `id` FROM `platform_projects` WHERE `slug` = 'default' LIMIT 1);

-- ============================================================================
-- Step 1: google_consoles -> platform_oauth_credentials
-- Legacy has no user_id/project_id — assign all to default project
-- Legacy `project_id` = Google Cloud project_id -> `cloud_project_id`
-- ============================================================================

INSERT INTO `platform_oauth_credentials` (
    `id`, `project_id`, `platform`, `name`, `cloud_project_id`,
    `client_id`, `client_secret`, `redirect_uris`, `credentials_file`,
    `description`, `enabled`, `created_at`, `updated_at`
)
SELECT
    gc.`id`,
    @default_project_id,
    'google',
    gc.`name`,
    gc.`project_id`,
    gc.`client_id`,
    gc.`client_secret`,
    gc.`redirect_uris`,
    gc.`credentials_file`,
    gc.`description`,
    COALESCE(gc.`enabled`, 1),
    gc.`created_at`,
    gc.`updated_at`
FROM `google_consoles` gc
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_oauth_credentials` poc WHERE poc.`id` = gc.`id`
);

-- ============================================================================
-- Step 2: youtube_channels -> platform_channels
-- channel_id -> platform_channel_id (rename to avoid PK confusion)
-- stat -> processing_status
-- console_name + add_info -> metadata JSON
-- ============================================================================

INSERT INTO `platform_channels` (
    `id`, `project_id`, `console_id`, `platform`, `name`,
    `platform_channel_id`, `access_token`, `refresh_token`,
    `token_expires_at`, `enabled`, `processing_status`, `metadata`,
    `created_at`, `updated_at`
)
SELECT
    yc.`id`,
    @default_project_id,
    yc.`console_id`,
    'youtube',
    yc.`name`,
    yc.`channel_id`,
    yc.`access_token`,
    yc.`refresh_token`,
    yc.`token_expires_at`,
    COALESCE(yc.`enabled`, 1),
    COALESCE(yc.`stat`, 0),
    -- Store legacy console_name and add_info in metadata JSON
    JSON_OBJECT(
        'legacy_console_name', yc.`console_name`,
        'legacy_add_info', yc.`add_info`
    ),
    yc.`created_at`,
    yc.`updated_at`
FROM `youtube_channels` yc
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = yc.`id`
);

-- ============================================================================
-- Step 3: youtube_tokens -> platform_channel_tokens
-- Legacy uses channel_name (string FK) -> resolve to channel_id (int FK)
-- ============================================================================

INSERT INTO `platform_channel_tokens` (
    `id`, `channel_id`, `token_type`, `token_value`, `expires_at`, `created_at`
)
SELECT
    yt.`id`,
    pc.`id`,
    yt.`token_type`,
    yt.`token_value`,
    yt.`expires_at`,
    yt.`created_at`
FROM `youtube_tokens` yt
INNER JOIN `platform_channels` pc ON pc.`name` = yt.`channel_name` AND pc.`platform` = 'youtube'
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channel_tokens` pct WHERE pct.`id` = yt.`id`
);

-- ============================================================================
-- Step 4: youtube_account_credentials -> platform_channel_login_credentials
-- Legacy uses channel_name (string FK) -> resolve to channel_id (int FK)
-- ============================================================================

INSERT INTO `platform_channel_login_credentials` (
    `id`, `channel_id`, `login_email`, `login_password`,
    `totp_secret`, `backup_codes`,
    `proxy_host`, `proxy_port`, `proxy_username`, `proxy_password`,
    `profile_path`, `user_agent`,
    `last_success_at`, `last_attempt_at`, `last_error`,
    `enabled`, `created_at`, `updated_at`
)
SELECT
    yac.`id`,
    pc.`id`,
    yac.`login_email`,
    yac.`login_password`,
    yac.`totp_secret`,
    yac.`backup_codes`,
    yac.`proxy_host`,
    yac.`proxy_port`,
    yac.`proxy_username`,
    yac.`proxy_password`,
    yac.`profile_path`,
    yac.`user_agent`,
    yac.`last_success_at`,
    yac.`last_attempt_at`,
    yac.`last_error`,
    COALESCE(yac.`enabled`, 1),
    yac.`created_at`,
    yac.`updated_at`
FROM `youtube_account_credentials` yac
INNER JOIN `platform_channels` pc ON pc.`name` = yac.`channel_name` AND pc.`platform` = 'youtube'
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channel_login_credentials` pclc WHERE pclc.`id` = yac.`id`
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate google_consoles, youtube_channels, youtube_tokens, youtube_account_credentials to new schema');
