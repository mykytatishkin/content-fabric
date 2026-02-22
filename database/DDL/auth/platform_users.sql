-- Reference DDL: platform_users
-- Replaces: user (legacy)
-- See: database/migrations/001_create_new_schema.sql

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
