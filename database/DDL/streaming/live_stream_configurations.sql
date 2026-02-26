-- Reference DDL: live_stream_configurations
-- Replaces: stream (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
