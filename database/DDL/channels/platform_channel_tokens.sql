-- Reference DDL: platform_channel_tokens
-- Replaces: youtube_tokens (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
