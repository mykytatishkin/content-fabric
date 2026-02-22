-- Reference DDL: platform_channels
-- Replaces: youtube_channels (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
