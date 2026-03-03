-- Reference DDL: platform_oauth_credentials
-- Replaces: google_consoles (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
