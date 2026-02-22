-- Reference DDL: channel_daily_statistics
-- Replaces: youtube_channel_daily (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
