CREATE TABLE `youtube_account` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Назва акаунта / каналу для UI',
  `client_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Google OAuth Client ID',
  `client_secret` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Google OAuth Client Secret',
  `access_token` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'OAuth access token',
  `refresh_token` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'OAuth refresh token',
  `token_expires` int unsigned DEFAULT NULL COMMENT 'Unix timestamp коли access_token протухає',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_token_expires` (`token_expires`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='YouTube OAuth accounts for Live Streaming'