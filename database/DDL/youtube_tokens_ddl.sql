CREATE TABLE `youtube_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `token_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `token_value` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_youtube_tokens_channel_expires` (`channel_name`,`expires_at`),
  CONSTRAINT `youtube_tokens_ibfk_1` FOREIGN KEY (`channel_name`) REFERENCES `youtube_channels` (`name`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci