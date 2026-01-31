-- ============================================
-- Channel Service: oauth_consoles
-- ============================================
-- OAuth credentials from cloud consoles (Google, TikTok, Meta)
-- Each console can be used by multiple channels

CREATE TABLE `oauth_consoles` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL COMMENT 'Owner of this console',
  `platform` varchar(50) NOT NULL DEFAULT 'google' COMMENT 'google, tiktok, meta',
  `name` varchar(255) NOT NULL COMMENT 'Human-readable name',
  `project_id` varchar(255) DEFAULT NULL COMMENT 'Cloud project ID',
  `client_id` text NOT NULL COMMENT 'OAuth Client ID',
  `client_secret` text NOT NULL COMMENT 'OAuth Client Secret',
  `redirect_uris` json DEFAULT NULL COMMENT 'OAuth redirect URIs',
  `credentials_file` varchar(500) DEFAULT NULL COMMENT 'Path to credentials.json (optional)',
  `description` text COMMENT 'Optional description',
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_platform_name` (`user_id`, `platform`, `name`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_platform` (`platform`),
  KEY `idx_enabled` (`enabled`),
  CONSTRAINT `fk_oauth_consoles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='OAuth console credentials - Channel Service';
