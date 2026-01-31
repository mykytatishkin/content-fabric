-- ============================================
-- Streaming Service: streaming_accounts
-- ============================================
-- OAuth accounts specifically for live streaming
-- Separate from channels as streaming uses different OAuth scopes

CREATE TABLE `streaming_accounts` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL COMMENT 'Owner of this streaming account',
  `platform` varchar(50) NOT NULL DEFAULT 'youtube' COMMENT 'youtube, twitch, etc.',
  `name` varchar(255) NOT NULL COMMENT 'Display name',
  `client_id` varchar(255) NOT NULL COMMENT 'OAuth Client ID',
  `client_secret` varchar(255) NOT NULL COMMENT 'OAuth Client Secret',
  `access_token` text NOT NULL,
  `refresh_token` text NOT NULL,
  `token_expires_at` int unsigned DEFAULT NULL COMMENT 'Unix timestamp',
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_platform_name` (`user_id`, `platform`, `name`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_platform` (`platform`),
  KEY `idx_token_expires` (`token_expires_at`),
  CONSTRAINT `fk_streaming_accounts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Streaming OAuth accounts - Streaming Service';
