-- ============================================
-- Channel Service: channels
-- ============================================
-- Multi-platform channels (YouTube, TikTok, Instagram)
-- Each channel belongs to a user

CREATE TABLE `channels` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL COMMENT 'Owner of this channel',
  `platform` varchar(50) NOT NULL DEFAULT 'youtube' COMMENT 'youtube, tiktok, instagram',
  `name` varchar(255) NOT NULL COMMENT 'Display name for UI',
  `platform_channel_id` varchar(255) NOT NULL COMMENT 'Platform-specific channel/account ID',
  `console_id` int unsigned DEFAULT NULL COMMENT 'Reference to oauth_consoles',
  `access_token` text COMMENT 'OAuth access token',
  `refresh_token` text COMMENT 'OAuth refresh token',
  `token_expires_at` datetime DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `stat` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Status flag for processing',
  `metadata` json DEFAULT NULL COMMENT 'Platform-specific metadata',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_platform_name` (`user_id`, `platform`, `name`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_platform` (`platform`),
  KEY `idx_console_id` (`console_id`),
  KEY `idx_enabled_created` (`enabled`, `created_at`),
  KEY `idx_token_expires` (`token_expires_at`),
  CONSTRAINT `fk_channels_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_channels_console` FOREIGN KEY (`console_id`) REFERENCES `oauth_consoles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Multi-platform channels - Channel Service';
