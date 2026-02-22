-- Reference DDL: channel_reauth_audit_logs
-- Replaces: youtube_reauth_audit (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
