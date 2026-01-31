-- ============================================
-- Channel Service: channel_credentials
-- ============================================
-- Login credentials for automated reauthorization (Playwright-based)
-- Sensitive data - ensure server access is restricted

CREATE TABLE `channel_credentials` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL COMMENT 'Reference to channels',
  `login_email` varchar(320) NOT NULL,
  `login_password` text NOT NULL COMMENT 'Encrypted password',
  `totp_secret` varchar(64) DEFAULT NULL COMMENT '2FA TOTP secret',
  `backup_codes` json DEFAULT NULL COMMENT '2FA backup codes',
  `proxy_host` varchar(255) DEFAULT NULL,
  `proxy_port` int DEFAULT NULL,
  `proxy_username` varchar(255) DEFAULT NULL,
  `proxy_password` varchar(255) DEFAULT NULL,
  `profile_path` varchar(500) DEFAULT NULL COMMENT 'Browser profile path',
  `user_agent` varchar(500) DEFAULT NULL,
  `last_success_at` datetime DEFAULT NULL,
  `last_attempt_at` datetime DEFAULT NULL,
  `last_error` text,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_channel_id` (`channel_id`),
  KEY `idx_login_email` (`login_email`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_last_success` (`last_success_at`),
  CONSTRAINT `fk_channel_credentials_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Reauth credentials - Channel Service';
