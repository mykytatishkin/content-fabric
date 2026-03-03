-- Reference DDL: live_streaming_accounts
-- Replaces: youtube_account (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
