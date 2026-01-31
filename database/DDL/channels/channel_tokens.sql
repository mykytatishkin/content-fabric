-- ============================================
-- Channel Service: channel_tokens
-- ============================================
-- Token history and backup for channels
-- Stores different types of tokens (access, refresh, etc.)

CREATE TABLE `channel_tokens` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL COMMENT 'Reference to channels',
  `token_type` varchar(100) NOT NULL COMMENT 'access_token, refresh_token, etc.',
  `token_value` text NOT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_channel_expires` (`channel_id`, `expires_at`),
  KEY `idx_token_type` (`token_type`),
  CONSTRAINT `fk_channel_tokens_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Token history - Channel Service';
