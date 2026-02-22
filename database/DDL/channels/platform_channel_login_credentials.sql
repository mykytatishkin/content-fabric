-- Reference DDL: platform_channel_login_credentials
-- Replaces: youtube_account_credentials (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
