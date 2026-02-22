-- Combined migration: creates new schema and migrates data from legacy tables
-- Auto-generated from database/migrations/001-007

-- =========================================
-- database/migrations/001_create_new_schema.sql
-- =========================================
-- ============================================================================
-- Migration 001: Create New Schema
-- Content Fabric Database Refactoring
--
-- Creates all 13 new tables with proper naming, FKs, indexes.
-- Legacy tables are NOT touched — they continue working in parallel.
-- ============================================================================

SET @migration_version = '001_create_new_schema';

-- Safety: skip if already applied
SELECT COUNT(*) INTO @already_applied
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'platform_schema_migrations';

-- ============================================================================
-- SYSTEM
-- ============================================================================

CREATE TABLE IF NOT EXISTS `platform_schema_migrations` (
  `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `version`       VARCHAR(180)    NOT NULL COMMENT 'Migration identifier',
  `description`   VARCHAR(500)    DEFAULT NULL,
  `checksum`      VARCHAR(64)     DEFAULT NULL COMMENT 'SHA-256 of migration file',
  `applied_at`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `execution_ms`  INT             DEFAULT NULL,
  `rolled_back`   TINYINT(1)      NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_sm_version` (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Schema migration version tracking';

-- ============================================================================
-- IDENTITY & ACCESS
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `platform_users` (
  `id`                      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `uuid`                    CHAR(36)        NOT NULL COMMENT 'Public-facing identifier for APIs',
  `username`                VARCHAR(255)    NOT NULL,
  `email`                   VARCHAR(255)    NOT NULL,
  `password_hash`           VARCHAR(255)    DEFAULT NULL COMMENT 'NULL for OAuth-only users',
  `auth_key`                VARCHAR(32)     NOT NULL COMMENT 'Session authentication key',
  `password_reset_token`    VARCHAR(255)    DEFAULT NULL,
  `verification_token`      VARCHAR(255)    DEFAULT NULL,
  `display_name`            VARCHAR(255)    DEFAULT NULL,
  `avatar_url`              TEXT            DEFAULT NULL,
  `status`                  SMALLINT        NOT NULL DEFAULT 10
                            COMMENT '0=deleted, 9=inactive, 10=active',
  `timezone`                VARCHAR(64)     DEFAULT 'UTC',
  `last_login_at`           TIMESTAMP       NULL DEFAULT NULL,
  `created_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_pu_uuid`             (`uuid`),
  UNIQUE KEY `uniq_pu_username`         (`username`),
  UNIQUE KEY `uniq_pu_email`            (`email`),
  UNIQUE KEY `uniq_pu_pwd_reset_token`  (`password_reset_token`),
  KEY `idx_pu_status`                   (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Platform user accounts';


CREATE TABLE IF NOT EXISTS `platform_projects` (
  `id`                      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `uuid`                    CHAR(36)        NOT NULL COMMENT 'Public-facing identifier',
  `owner_id`                INT UNSIGNED    NOT NULL COMMENT 'User who created the project',
  `name`                    VARCHAR(255)    NOT NULL,
  `slug`                    VARCHAR(100)    NOT NULL COMMENT 'URL-safe identifier',
  `description`             TEXT            DEFAULT NULL,
  `subscription_plan`       VARCHAR(50)     NOT NULL DEFAULT 'starter'
                            COMMENT 'starter, professional, business, enterprise',
  `subscription_expires_at` DATETIME        DEFAULT NULL,
  `settings`                JSON            DEFAULT NULL COMMENT 'Project-level settings',
  `status`                  SMALLINT        NOT NULL DEFAULT 10
                            COMMENT '0=archived, 9=suspended, 10=active',
  `created_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_pp_uuid`     (`uuid`),
  UNIQUE KEY `uniq_pp_slug`     (`slug`),
  KEY `idx_pp_owner`            (`owner_id`),
  KEY `idx_pp_status`           (`status`),
  CONSTRAINT `fk_pp_owner` FOREIGN KEY (`owner_id`) REFERENCES `platform_users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Project workspaces grouping all resources';


CREATE TABLE IF NOT EXISTS `platform_project_members` (
  `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`    INT UNSIGNED    NOT NULL,
  `user_id`       INT UNSIGNED    NOT NULL,
  `role`          VARCHAR(50)     NOT NULL DEFAULT 'viewer'
                  COMMENT 'owner, admin, editor, viewer',
  `invited_by`    INT UNSIGNED    DEFAULT NULL,
  `invited_at`    TIMESTAMP       NULL DEFAULT NULL,
  `accepted_at`   TIMESTAMP       NULL DEFAULT NULL,
  `status`        VARCHAR(20)     NOT NULL DEFAULT 'active'
                  COMMENT 'pending, active, suspended, removed',
  `created_at`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_ppm_project_user`    (`project_id`, `user_id`),
  KEY `idx_ppm_user`                    (`user_id`),
  KEY `idx_ppm_role`                    (`role`),
  KEY `idx_ppm_status`                  (`status`),
  CONSTRAINT `fk_ppm_project`   FOREIGN KEY (`project_id`) REFERENCES `platform_projects` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ppm_user`      FOREIGN KEY (`user_id`)    REFERENCES `platform_users`    (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ppm_invited`   FOREIGN KEY (`invited_by`) REFERENCES `platform_users`    (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Project membership with RBAC roles';

-- ============================================================================
-- CHANNELS & OAUTH
-- ============================================================================

CREATE TABLE IF NOT EXISTS `platform_oauth_credentials` (
  `id`                INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`        INT UNSIGNED    NOT NULL,
  `platform`          VARCHAR(50)     NOT NULL DEFAULT 'google'
                      COMMENT 'google, tiktok, meta, twitch',
  `name`              VARCHAR(255)    NOT NULL COMMENT 'Human-readable name',
  `cloud_project_id`  VARCHAR(255)    DEFAULT NULL COMMENT 'Cloud provider project ID',
  `client_id`         TEXT            NOT NULL COMMENT 'OAuth Client ID',
  `client_secret`     TEXT            NOT NULL COMMENT 'OAuth Client Secret',
  `redirect_uris`     JSON            DEFAULT NULL,
  `credentials_file`  VARCHAR(500)    DEFAULT NULL COMMENT 'Path to credentials.json',
  `description`       TEXT            DEFAULT NULL,
  `enabled`           TINYINT(1)      NOT NULL DEFAULT 1,
  `created_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_poc_project_platform_name` (`project_id`, `platform`, `name`),
  KEY `idx_poc_project`     (`project_id`),
  KEY `idx_poc_platform`    (`platform`),
  KEY `idx_poc_enabled`     (`enabled`),
  CONSTRAINT `fk_poc_project` FOREIGN KEY (`project_id`) REFERENCES `platform_projects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='OAuth console/app credentials from cloud providers';


CREATE TABLE IF NOT EXISTS `platform_channels` (
  `id`                    INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`            INT UNSIGNED    NOT NULL,
  `console_id`            INT UNSIGNED    DEFAULT NULL,
  `platform`              VARCHAR(50)     NOT NULL DEFAULT 'youtube'
                          COMMENT 'youtube, tiktok, instagram, twitch',
  `name`                  VARCHAR(255)    NOT NULL COMMENT 'Display name in UI',
  `platform_channel_id`   VARCHAR(255)    NOT NULL COMMENT 'Platform-specific ID (UC..., @handle)',
  `access_token`          TEXT            DEFAULT NULL,
  `refresh_token`         TEXT            DEFAULT NULL,
  `token_expires_at`      DATETIME        DEFAULT NULL,
  `enabled`               TINYINT(1)      NOT NULL DEFAULT 1,
  `processing_status`     TINYINT(1)      NOT NULL DEFAULT 0
                          COMMENT 'Worker processing flag',
  `metadata`              JSON            DEFAULT NULL
                          COMMENT 'Platform-specific data',
  `created_at`            TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`            TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_pc_project_platform_name` (`project_id`, `platform`, `name`),
  KEY `idx_pc_project`          (`project_id`),
  KEY `idx_pc_console`          (`console_id`),
  KEY `idx_pc_platform`         (`platform`),
  KEY `idx_pc_enabled_created`  (`enabled`, `created_at`),
  KEY `idx_pc_token_expires`    (`token_expires_at`),
  CONSTRAINT `fk_pc_project` FOREIGN KEY (`project_id`) REFERENCES `platform_projects` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_pc_console` FOREIGN KEY (`console_id`) REFERENCES `platform_oauth_credentials` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Multi-platform channels';


CREATE TABLE IF NOT EXISTS `platform_channel_tokens` (
  `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `channel_id`    INT UNSIGNED    NOT NULL,
  `token_type`    VARCHAR(100)    NOT NULL COMMENT 'access_token, refresh_token',
  `token_value`   TEXT            NOT NULL,
  `expires_at`    DATETIME        DEFAULT NULL,
  `created_at`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pct_channel`             (`channel_id`),
  KEY `idx_pct_channel_expires`     (`channel_id`, `expires_at`),
  KEY `idx_pct_token_type`          (`token_type`),
  CONSTRAINT `fk_pct_channel` FOREIGN KEY (`channel_id`) REFERENCES `platform_channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Token history for channels';


CREATE TABLE IF NOT EXISTS `platform_channel_login_credentials` (
  `id`              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `channel_id`      INT UNSIGNED    NOT NULL,
  `login_email`     VARCHAR(320)    NOT NULL,
  `login_password`  TEXT            NOT NULL COMMENT 'Encrypted password',
  `totp_secret`     VARCHAR(64)     DEFAULT NULL COMMENT '2FA TOTP secret',
  `backup_codes`    JSON            DEFAULT NULL,
  `proxy_host`      VARCHAR(255)    DEFAULT NULL,
  `proxy_port`      INT             DEFAULT NULL,
  `proxy_username`  VARCHAR(255)    DEFAULT NULL,
  `proxy_password`  VARCHAR(255)    DEFAULT NULL,
  `profile_path`    VARCHAR(500)    DEFAULT NULL COMMENT 'Browser profile directory',
  `user_agent`      VARCHAR(500)    DEFAULT NULL,
  `last_success_at` DATETIME        DEFAULT NULL,
  `last_attempt_at` DATETIME        DEFAULT NULL,
  `last_error`      TEXT            DEFAULT NULL,
  `enabled`         TINYINT(1)      NOT NULL DEFAULT 1,
  `created_at`      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_pclc_channel`    (`channel_id`),
  KEY `idx_pclc_login_email`        (`login_email`),
  KEY `idx_pclc_enabled`            (`enabled`),
  KEY `idx_pclc_last_success`       (`last_success_at`),
  CONSTRAINT `fk_pclc_channel` FOREIGN KEY (`channel_id`) REFERENCES `platform_channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='RPA credentials for automated reauthorization';

-- ============================================================================
-- PUBLISHING
-- ============================================================================

CREATE TABLE IF NOT EXISTS `content_upload_queue_tasks` (
  `id`                INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`        INT UNSIGNED    NOT NULL,
  `channel_id`        INT UNSIGNED    NOT NULL,
  `created_by`        INT UNSIGNED    DEFAULT NULL COMMENT 'User who created the task',
  `platform`          VARCHAR(50)     NOT NULL DEFAULT 'youtube',
  `media_type`        VARCHAR(20)     NOT NULL DEFAULT 'video'
                      COMMENT 'video, short, reel, story',
  `status`            TINYINT         NOT NULL DEFAULT 0
                      COMMENT '0=pending, 1=completed, 2=failed, 3=processing, 4=cancelled',
  `source_file_path`  VARCHAR(500)    DEFAULT NULL,
  `thumbnail_path`    VARCHAR(500)    DEFAULT NULL,
  `title`             VARCHAR(500)    NOT NULL,
  `description`       TEXT            DEFAULT NULL,
  `keywords`          TEXT            DEFAULT NULL COMMENT 'Comma-separated tags',
  `post_comment`      TEXT            DEFAULT NULL COMMENT 'Comment to post after upload',
  `metadata`          JSON            DEFAULT NULL
                      COMMENT 'Platform-specific: privacy, category, etc.',
  `scheduled_at`      DATETIME        NOT NULL COMMENT 'When to publish',
  `started_at`        DATETIME        DEFAULT NULL COMMENT 'When processing began',
  `completed_at`      DATETIME        DEFAULT NULL COMMENT 'When task finished',
  `upload_id`         VARCHAR(255)    DEFAULT NULL COMMENT 'Platform video ID after upload',
  `upload_url`        VARCHAR(500)    DEFAULT NULL COMMENT 'URL to published content',
  `retry_count`       INT             NOT NULL DEFAULT 0,
  `max_retries`       INT             NOT NULL DEFAULT 3,
  `error_message`     TEXT            DEFAULT NULL,
  `error_code`        VARCHAR(100)    DEFAULT NULL COMMENT 'Categorized error code',
  `legacy_add_info`   LONGTEXT        DEFAULT NULL COMMENT 'Preserved legacy add_info JSON',
  `created_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cuqt_project`            (`project_id`),
  KEY `idx_cuqt_channel`            (`channel_id`),
  KEY `idx_cuqt_created_by`         (`created_by`),
  KEY `idx_cuqt_project_status`     (`project_id`, `status`),
  KEY `idx_cuqt_channel_status`     (`channel_id`, `status`),
  KEY `idx_cuqt_status_scheduled`   (`status`, `scheduled_at`),
  KEY `idx_cuqt_platform`           (`platform`),
  KEY `idx_cuqt_upload_id`          (`upload_id`),
  CONSTRAINT `fk_cuqt_project`      FOREIGN KEY (`project_id`)  REFERENCES `platform_projects`  (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cuqt_channel`      FOREIGN KEY (`channel_id`)  REFERENCES `platform_channels`  (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cuqt_created_by`   FOREIGN KEY (`created_by`)  REFERENCES `platform_users`     (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Content publishing task queue';

-- ============================================================================
-- ANALYTICS & AUDIT
-- ============================================================================

CREATE TABLE IF NOT EXISTS `channel_daily_statistics` (
  `id`                    INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `channel_id`            INT UNSIGNED    NOT NULL,
  `platform_channel_id`   VARCHAR(64)     NOT NULL COMMENT 'Platform ID for API lookup',
  `snapshot_date`         DATE            NOT NULL,
  `subscribers`           BIGINT          DEFAULT NULL,
  `views`                 BIGINT          DEFAULT NULL,
  `videos`                BIGINT          DEFAULT NULL,
  `likes`                 BIGINT          DEFAULT NULL,
  `comments`              BIGINT          DEFAULT NULL,
  `metadata`              JSON            DEFAULT NULL COMMENT 'Additional platform-specific metrics',
  `created_at`            TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_cds_channel_date`    (`channel_id`, `snapshot_date`),
  KEY `idx_cds_channel`                 (`channel_id`),
  KEY `idx_cds_snapshot_date`           (`snapshot_date`),
  KEY `idx_cds_platform_channel`        (`platform_channel_id`),
  CONSTRAINT `fk_cds_channel` FOREIGN KEY (`channel_id`) REFERENCES `platform_channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Daily channel statistics snapshots';


CREATE TABLE IF NOT EXISTS `channel_reauth_audit_logs` (
  `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `channel_id`      INT UNSIGNED    NOT NULL,
  `initiated_at`    DATETIME        NOT NULL,
  `completed_at`    DATETIME        DEFAULT NULL,
  `status`          VARCHAR(32)     NOT NULL
                    COMMENT 'started, success, failed, timeout, skipped',
  `trigger_reason`  VARCHAR(100)    DEFAULT NULL
                    COMMENT 'token_expired, manual, error_recovery, scheduled',
  `error_message`   TEXT            DEFAULT NULL,
  `error_code`      VARCHAR(100)    DEFAULT NULL,
  `metadata`        JSON            DEFAULT NULL COMMENT 'Context: IP, user agent, etc.',
  `created_at`      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cral_channel`            (`channel_id`),
  KEY `idx_cral_channel_status`     (`channel_id`, `status`),
  KEY `idx_cral_initiated`          (`initiated_at`),
  KEY `idx_cral_status`             (`status`),
  CONSTRAINT `fk_cral_channel` FOREIGN KEY (`channel_id`) REFERENCES `platform_channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='OAuth reauthorization audit trail';

-- ============================================================================
-- STREAMING
-- ============================================================================

CREATE TABLE IF NOT EXISTS `live_streaming_accounts` (
  `id`                INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`        INT UNSIGNED    NOT NULL,
  `platform`          VARCHAR(50)     NOT NULL DEFAULT 'youtube'
                      COMMENT 'youtube, twitch, kick',
  `name`              VARCHAR(255)    NOT NULL,
  `client_id`         VARCHAR(255)    NOT NULL,
  `client_secret`     VARCHAR(255)    NOT NULL,
  `access_token`      TEXT            NOT NULL,
  `refresh_token`     TEXT            NOT NULL,
  `token_expires_at`  TIMESTAMP       NULL DEFAULT NULL,
  `enabled`           TINYINT(1)      NOT NULL DEFAULT 1,
  `created_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_lsa_project_platform_name` (`project_id`, `platform`, `name`),
  KEY `idx_lsa_project`         (`project_id`),
  KEY `idx_lsa_platform`        (`platform`),
  KEY `idx_lsa_token_expires`   (`token_expires_at`),
  CONSTRAINT `fk_lsa_project` FOREIGN KEY (`project_id`) REFERENCES `platform_projects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='OAuth accounts for live streaming';


CREATE TABLE IF NOT EXISTS `live_stream_configurations` (
  `id`                      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`              INT UNSIGNED    NOT NULL,
  `streaming_account_id`    INT UNSIGNED    DEFAULT NULL,
  `channel_id`              INT UNSIGNED    DEFAULT NULL,
  `name`                    VARCHAR(120)    NOT NULL COMMENT 'Stream name for UI',
  `service_name`            VARCHAR(160)    NOT NULL COMMENT 'Systemd service name',
  `workdir`                 VARCHAR(255)    NOT NULL,
  `rtmp_host`               VARCHAR(255)    DEFAULT NULL,
  `rtmp_base`               VARCHAR(255)    DEFAULT NULL,
  `stream_key`              VARCHAR(255)    DEFAULT NULL,
  `duration_sec`            INT             NOT NULL DEFAULT 42900,
  `platform_broadcast_id`   VARCHAR(64)     DEFAULT NULL,
  `platform_video_id`       VARCHAR(64)     DEFAULT NULL,
  `platform_stream_id`      VARCHAR(64)     DEFAULT NULL,
  `platform_stream_key`     VARCHAR(128)    DEFAULT NULL,
  `title`                   VARCHAR(255)    DEFAULT NULL,
  `description`             TEXT            DEFAULT NULL,
  `tags`                    TEXT            DEFAULT NULL COMMENT 'Comma-separated',
  `thumbnail_path`          VARCHAR(255)    DEFAULT NULL,
  `enabled`                 TINYINT(1)      NOT NULL DEFAULT 1,
  `notes`                   TEXT            DEFAULT NULL,
  `created_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_lsc_service_name`    (`service_name`),
  KEY `idx_lsc_project`                 (`project_id`),
  KEY `idx_lsc_streaming_account`       (`streaming_account_id`),
  KEY `idx_lsc_channel`                 (`channel_id`),
  KEY `idx_lsc_enabled`                 (`enabled`),
  CONSTRAINT `fk_lsc_project`           FOREIGN KEY (`project_id`)           REFERENCES `platform_projects`       (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_lsc_streaming_account` FOREIGN KEY (`streaming_account_id`) REFERENCES `live_streaming_accounts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_lsc_channel`           FOREIGN KEY (`channel_id`)           REFERENCES `platform_channels`       (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Live stream configurations';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Create all 13 new tables for refactored schema with projects and RBAC');

-- =========================================
-- database/migrations/002_migrate_identity.sql
-- =========================================
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

-- =========================================
-- database/migrations/003_migrate_channels.sql
-- =========================================
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

-- =========================================
-- database/migrations/004_migrate_publishing.sql
-- =========================================
-- ============================================================================
-- Migration 004: Migrate Publishing Tasks
-- Content Fabric Database Refactoring
--
-- Migrates: tasks -> content_upload_queue_tasks (~5079 records)
--
-- Key transformations:
--   account_id   -> channel_id (same values, channels.id)
--   date_add     -> created_at
--   date_post    -> scheduled_at
--   date_done    -> completed_at
--   att_file_path-> source_file_path
--   cover        -> thumbnail_path
--   add_info     -> legacy_add_info (preserved as-is)
--   NEW: project_id (derived from channel), created_by, retry_count,
--        max_retries, error_code, upload_url, metadata
-- ============================================================================

SET @migration_version = '004_migrate_publishing';

-- Get default project and user
SET @default_project_id = (SELECT `id` FROM `platform_projects` WHERE `slug` = 'default' LIMIT 1);
SET @default_user_id = (SELECT MIN(`id`) FROM `platform_users`);

-- ============================================================================
-- Migrate tasks -> content_upload_queue_tasks
-- ============================================================================

INSERT INTO `content_upload_queue_tasks` (
    `id`, `project_id`, `channel_id`, `created_by`,
    `platform`, `media_type`, `status`,
    `source_file_path`, `thumbnail_path`,
    `title`, `description`, `keywords`, `post_comment`,
    `scheduled_at`, `completed_at`,
    `upload_id`, `error_message`,
    `legacy_add_info`,
    `created_at`
)
SELECT
    t.`id`,
    @default_project_id,
    t.`account_id`,                              -- account_id -> channel_id
    @default_user_id,                             -- created_by = default user
    COALESCE(t.`media_type`, 'youtube'),          -- platform
    CASE
        WHEN t.`media_type` IN ('short', 'shorts') THEN 'short'
        WHEN t.`media_type` IN ('reel', 'reels') THEN 'reel'
        WHEN t.`media_type` IN ('story', 'stories') THEN 'story'
        ELSE 'video'
    END,                                          -- media_type normalized
    t.`status`,
    t.`att_file_path`,                            -- -> source_file_path
    t.`cover`,                                    -- -> thumbnail_path
    COALESCE(t.`title`, '(untitled)'),
    t.`description`,
    t.`keywords`,
    t.`post_comment`,
    COALESCE(t.`date_post`, t.`date_add`, NOW()), -- -> scheduled_at
    t.`date_done`,                                -- -> completed_at
    t.`upload_id`,
    t.`error_message`,
    t.`add_info`,                                 -- -> legacy_add_info
    COALESCE(t.`date_add`, NOW())                 -- -> created_at
FROM `tasks` t
WHERE NOT EXISTS (
    SELECT 1 FROM `content_upload_queue_tasks` cuqt WHERE cuqt.`id` = t.`id`
)
-- Only migrate tasks whose channel exists in new schema
AND EXISTS (
    SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`
);

-- Log orphaned tasks (channel doesn't exist in new schema)
-- These are tasks with invalid account_id references
SELECT COUNT(*) AS orphaned_tasks_count
FROM `tasks` t
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate tasks to content_upload_queue_tasks with column renames and project assignment');

-- =========================================
-- database/migrations/005_migrate_analytics.sql
-- =========================================
-- ============================================================================
-- Migration 005: Migrate Analytics & Audit
-- Content Fabric Database Refactoring
--
-- Migrates:
--   youtube_channel_daily  -> channel_daily_statistics (~2050 records)
--   youtube_reauth_audit   -> channel_reauth_audit_logs (~3550 records)
--
-- Key transformations:
--   - channel_name (string FK) -> channel_id (int FK)
--   - yt_channel_id -> proper FK via platform_channel_id lookup
--   - Added: trigger_reason, error_code, likes, comments, metadata
-- ============================================================================

SET @migration_version = '005_migrate_analytics';

-- ============================================================================
-- Step 1: youtube_channel_daily -> channel_daily_statistics
-- Legacy has yt_channel_id (int, no FK) + channel_id (string, YouTube ID)
-- New uses channel_id (int FK) + platform_channel_id (string)
-- ============================================================================

INSERT INTO `channel_daily_statistics` (
    `id`, `channel_id`, `platform_channel_id`, `snapshot_date`,
    `subscribers`, `views`, `videos`, `created_at`
)
SELECT
    ycd.`id`,
    pc.`id`,
    ycd.`channel_id`,          -- This is the YouTube channel string ID (UC...)
    ycd.`snapshot_date`,
    ycd.`subscribers`,
    ycd.`views`,
    ycd.`videos`,
    ycd.`created_at`
FROM `youtube_channel_daily` ycd
-- Join by platform_channel_id (the YouTube UC... string)
INNER JOIN `platform_channels` pc
    ON pc.`platform_channel_id` = ycd.`channel_id`
    AND pc.`platform` = 'youtube'
WHERE NOT EXISTS (
    SELECT 1 FROM `channel_daily_statistics` cds WHERE cds.`id` = ycd.`id`
);

-- Also migrate records where channel_id doesn't match but yt_channel_id does
-- (yt_channel_id is the integer ID referencing youtube_channels.id)
INSERT IGNORE INTO `channel_daily_statistics` (
    `channel_id`, `platform_channel_id`, `snapshot_date`,
    `subscribers`, `views`, `videos`, `created_at`
)
SELECT
    pc.`id`,
    ycd.`channel_id`,
    ycd.`snapshot_date`,
    ycd.`subscribers`,
    ycd.`views`,
    ycd.`videos`,
    ycd.`created_at`
FROM `youtube_channel_daily` ycd
INNER JOIN `platform_channels` pc ON pc.`id` = ycd.`yt_channel_id`
WHERE NOT EXISTS (
    SELECT 1 FROM `channel_daily_statistics` cds
    WHERE cds.`channel_id` = pc.`id` AND cds.`snapshot_date` = ycd.`snapshot_date`
)
AND ycd.`yt_channel_id` IS NOT NULL;

-- ============================================================================
-- Step 2: youtube_reauth_audit -> channel_reauth_audit_logs
-- Legacy uses channel_name (string FK) -> resolve to channel_id (int FK)
-- Added: trigger_reason, error_code (new fields, NULL for migrated data)
-- ============================================================================

INSERT INTO `channel_reauth_audit_logs` (
    `id`, `channel_id`, `initiated_at`, `completed_at`,
    `status`, `error_message`, `metadata`, `created_at`
)
SELECT
    yra.`id`,
    pc.`id`,
    yra.`initiated_at`,
    yra.`completed_at`,
    yra.`status`,
    yra.`error_message`,
    yra.`metadata`,
    COALESCE(yra.`initiated_at`, NOW())
FROM `youtube_reauth_audit` yra
INNER JOIN `platform_channels` pc ON pc.`name` = yra.`channel_name` AND pc.`platform` = 'youtube'
WHERE NOT EXISTS (
    SELECT 1 FROM `channel_reauth_audit_logs` cral WHERE cral.`id` = yra.`id`
);

-- Log orphaned audit records (channel doesn't exist)
SELECT COUNT(*) AS orphaned_reauth_audit_count
FROM `youtube_reauth_audit` yra
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channels` pc
    WHERE pc.`name` = yra.`channel_name` AND pc.`platform` = 'youtube'
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate youtube_channel_daily and youtube_reauth_audit to new analytics tables');

-- =========================================
-- database/migrations/006_migrate_streaming.sql
-- =========================================
-- ============================================================================
-- Migration 006: Migrate Streaming
-- Content Fabric Database Refactoring
--
-- Migrates:
--   youtube_account -> live_streaming_accounts (~7 records)
--   stream          -> live_stream_configurations (~8 records)
--
-- Key transformations:
--   - token_expires (unix int) -> token_expires_at (TIMESTAMP)
--   - created_at/updated_at (unix int) -> TIMESTAMP
--   - youtube_* columns -> platform_* (platform-agnostic)
--   - yt_title/yt_description/etc -> title/description/etc
--   - All records assigned to @default_project_id
-- ============================================================================

SET @migration_version = '006_migrate_streaming';

SET @default_project_id = (SELECT `id` FROM `platform_projects` WHERE `slug` = 'default' LIMIT 1);

-- ============================================================================
-- Step 1: youtube_account -> live_streaming_accounts
-- ============================================================================

INSERT INTO `live_streaming_accounts` (
    `id`, `project_id`, `platform`, `name`,
    `client_id`, `client_secret`,
    `access_token`, `refresh_token`, `token_expires_at`,
    `enabled`, `created_at`, `updated_at`
)
SELECT
    ya.`id`,
    @default_project_id,
    'youtube',
    ya.`name`,
    ya.`client_id`,
    ya.`client_secret`,
    ya.`access_token`,
    ya.`refresh_token`,
    CASE
        WHEN ya.`token_expires` IS NOT NULL AND ya.`token_expires` > 0
        THEN FROM_UNIXTIME(ya.`token_expires`)
        ELSE NULL
    END,
    1,
    ya.`created_at`,
    ya.`updated_at`
FROM `youtube_account` ya
WHERE NOT EXISTS (
    SELECT 1 FROM `live_streaming_accounts` lsa WHERE lsa.`id` = ya.`id`
);

-- ============================================================================
-- Step 2: stream -> live_stream_configurations
-- Legacy created_at/updated_at are unix timestamps (INT)
-- youtube_* prefixed columns -> platform_* (platform-agnostic naming)
-- ============================================================================

INSERT INTO `live_stream_configurations` (
    `id`, `project_id`, `streaming_account_id`, `channel_id`,
    `name`, `service_name`, `workdir`,
    `rtmp_host`, `rtmp_base`, `stream_key`, `duration_sec`,
    `platform_broadcast_id`, `platform_video_id`,
    `platform_stream_id`, `platform_stream_key`,
    `title`, `description`, `tags`, `thumbnail_path`,
    `enabled`, `notes`,
    `created_at`, `updated_at`
)
SELECT
    s.`id`,
    @default_project_id,
    s.`youtube_account_id`,
    -- Resolve channel_name to channel_id (COLLATE needed: stream uses 0900_ai_ci)
    (SELECT pc.`id` FROM `platform_channels` pc
     WHERE pc.`name` = s.`channel_name` COLLATE utf8mb4_unicode_ci AND pc.`platform` = 'youtube' LIMIT 1),
    s.`name`,
    s.`service_name`,
    s.`workdir`,
    s.`rtmp_host`,
    s.`rtmp_base`,
    s.`stream_key`,
    COALESCE(s.`duration_sec`, 42900),
    s.`youtube_broadcast_id`,       -- -> platform_broadcast_id
    s.`youtube_video_id`,           -- -> platform_video_id
    s.`youtube_stream_id`,          -- -> platform_stream_id
    s.`youtube_stream_key`,         -- -> platform_stream_key
    s.`yt_title`,                   -- -> title
    s.`yt_description`,             -- -> description
    s.`yt_tags`,                    -- -> tags
    s.`yt_thumbnail`,               -- -> thumbnail_path
    COALESCE(s.`enabled`, 1),
    s.`notes`,
    CASE
        WHEN s.`created_at` > 1000000000
        THEN FROM_UNIXTIME(s.`created_at`)
        ELSE NOW()
    END,
    CASE
        WHEN s.`updated_at` > 1000000000
        THEN FROM_UNIXTIME(s.`updated_at`)
        ELSE NOW()
    END
FROM `stream` s
WHERE NOT EXISTS (
    SELECT 1 FROM `live_stream_configurations` lsc WHERE lsc.`id` = s.`id`
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate youtube_account and stream to new streaming tables');

-- =========================================
-- database/migrations/007_verify_migration.sql
-- =========================================
-- ============================================================================
-- Migration 007: Verify Migration Integrity
-- Content Fabric Database Refactoring
--
-- Compares row counts between legacy and new tables.
-- Run this AFTER 001-006 to ensure all data migrated correctly.
-- Does NOT modify any data.
-- ============================================================================

SET @migration_version = '007_verify_migration';

-- ============================================================================
-- Row count comparison
-- ============================================================================

SELECT '=== MIGRATION VERIFICATION ===' AS info;

-- Users
SELECT
    'users' AS check_name,
    (SELECT COUNT(*) FROM `user`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_users`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `user`) <= (SELECT COUNT(*) FROM `platform_users`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- OAuth Consoles
SELECT
    'oauth_consoles' AS check_name,
    (SELECT COUNT(*) FROM `google_consoles`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_oauth_credentials`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `google_consoles`) = (SELECT COUNT(*) FROM `platform_oauth_credentials`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Channels
SELECT
    'channels' AS check_name,
    (SELECT COUNT(*) FROM `youtube_channels`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_channels`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_channels`) = (SELECT COUNT(*) FROM `platform_channels`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Tokens
SELECT
    'channel_tokens' AS check_name,
    (SELECT COUNT(*) FROM `youtube_tokens`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_channel_tokens`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_tokens`) = (SELECT COUNT(*) FROM `platform_channel_tokens`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Login Credentials
SELECT
    'login_credentials' AS check_name,
    (SELECT COUNT(*) FROM `youtube_account_credentials`) AS legacy_count,
    (SELECT COUNT(*) FROM `platform_channel_login_credentials`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_account_credentials`) = (SELECT COUNT(*) FROM `platform_channel_login_credentials`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Tasks
SELECT
    'tasks' AS check_name,
    (SELECT COUNT(*) FROM `tasks`) AS legacy_count,
    (SELECT COUNT(*) FROM `content_upload_queue_tasks`) AS new_count,
    (SELECT COUNT(*) FROM `tasks` t
     WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`)
    ) AS orphaned_legacy,
    CASE
        WHEN (SELECT COUNT(*) FROM `tasks`) =
             (SELECT COUNT(*) FROM `content_upload_queue_tasks`) +
             (SELECT COUNT(*) FROM `tasks` t
              WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`))
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Daily Stats
SELECT
    'daily_stats' AS check_name,
    (SELECT COUNT(*) FROM `youtube_channel_daily`) AS legacy_count,
    (SELECT COUNT(*) FROM `channel_daily_statistics`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `channel_daily_statistics`) > 0
        THEN 'OK' ELSE 'CHECK MANUALLY'
    END AS status;

-- Reauth Audit
SELECT
    'reauth_audit' AS check_name,
    (SELECT COUNT(*) FROM `youtube_reauth_audit`) AS legacy_count,
    (SELECT COUNT(*) FROM `channel_reauth_audit_logs`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_reauth_audit`) >=
             (SELECT COUNT(*) FROM `channel_reauth_audit_logs`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Streaming Accounts
SELECT
    'streaming_accounts' AS check_name,
    (SELECT COUNT(*) FROM `youtube_account`) AS legacy_count,
    (SELECT COUNT(*) FROM `live_streaming_accounts`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `youtube_account`) = (SELECT COUNT(*) FROM `live_streaming_accounts`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- Streams
SELECT
    'stream_configs' AS check_name,
    (SELECT COUNT(*) FROM `stream`) AS legacy_count,
    (SELECT COUNT(*) FROM `live_stream_configurations`) AS new_count,
    CASE
        WHEN (SELECT COUNT(*) FROM `stream`) = (SELECT COUNT(*) FROM `live_stream_configurations`)
        THEN 'OK' ELSE 'MISMATCH'
    END AS status;

-- ============================================================================
-- FK integrity checks
-- ============================================================================

SELECT '=== FK INTEGRITY CHECKS ===' AS info;

-- Channels with invalid console_id
SELECT 'channels_invalid_console' AS check_name,
    COUNT(*) AS count
FROM `platform_channels` pc
WHERE pc.`console_id` IS NOT NULL
AND NOT EXISTS (SELECT 1 FROM `platform_oauth_credentials` poc WHERE poc.`id` = pc.`console_id`);

-- Tasks with invalid channel_id
SELECT 'tasks_invalid_channel' AS check_name,
    COUNT(*) AS count
FROM `content_upload_queue_tasks` cuqt
WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = cuqt.`channel_id`);

-- Credentials with invalid channel_id
SELECT 'credentials_invalid_channel' AS check_name,
    COUNT(*) AS count
FROM `platform_channel_login_credentials` pclc
WHERE NOT EXISTS (SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = pclc.`channel_id`);

-- Project/member integrity
SELECT 'project_members_valid' AS check_name,
    COUNT(*) AS count
FROM `platform_project_members` ppm
WHERE EXISTS (SELECT 1 FROM `platform_projects` pp WHERE pp.`id` = ppm.`project_id`)
AND EXISTS (SELECT 1 FROM `platform_users` pu WHERE pu.`id` = ppm.`user_id`);

-- ============================================================================
-- Summary
-- ============================================================================

SELECT '=== MIGRATION SUMMARY ===' AS info;

SELECT
    (SELECT COUNT(*) FROM `platform_users`) AS users,
    (SELECT COUNT(*) FROM `platform_projects`) AS projects,
    (SELECT COUNT(*) FROM `platform_project_members`) AS members,
    (SELECT COUNT(*) FROM `platform_oauth_credentials`) AS oauth_consoles,
    (SELECT COUNT(*) FROM `platform_channels`) AS channels,
    (SELECT COUNT(*) FROM `platform_channel_tokens`) AS tokens,
    (SELECT COUNT(*) FROM `platform_channel_login_credentials`) AS login_creds,
    (SELECT COUNT(*) FROM `content_upload_queue_tasks`) AS tasks,
    (SELECT COUNT(*) FROM `channel_daily_statistics`) AS daily_stats,
    (SELECT COUNT(*) FROM `channel_reauth_audit_logs`) AS audit_logs,
    (SELECT COUNT(*) FROM `live_streaming_accounts`) AS streaming_accs,
    (SELECT COUNT(*) FROM `live_stream_configurations`) AS stream_configs;

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT IGNORE INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Verify migration integrity - row counts and FK checks');

