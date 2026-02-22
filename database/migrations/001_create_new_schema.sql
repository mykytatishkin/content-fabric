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
