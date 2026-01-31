-- ============================================
-- Auth Service: users
-- ============================================
-- User accounts for the Content Factory platform
-- Supports both password and OAuth authentication

CREATE TABLE `users` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL COMMENT 'Public UUID for API exposure',
  `username` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) DEFAULT NULL COMMENT 'NULL if OAuth-only user',
  `auth_key` varchar(32) NOT NULL COMMENT 'Session auth key',
  `password_reset_token` varchar(255) DEFAULT NULL,
  `verification_token` varchar(255) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL COMMENT 'Display name',
  `avatar_url` text DEFAULT NULL,
  `status` smallint NOT NULL DEFAULT 10 COMMENT '0=deleted, 9=inactive, 10=active',
  `subscription_plan` varchar(50) NOT NULL DEFAULT 'starter' COMMENT 'starter, professional, business, enterprise',
  `subscription_expires_at` datetime DEFAULT NULL,
  `timezone` varchar(64) DEFAULT 'UTC',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_uuid` (`uuid`),
  UNIQUE KEY `uniq_username` (`username`),
  UNIQUE KEY `uniq_email` (`email`),
  UNIQUE KEY `uniq_password_reset_token` (`password_reset_token`),
  KEY `idx_status` (`status`),
  KEY `idx_subscription` (`subscription_plan`, `subscription_expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Platform users - Auth Service';
