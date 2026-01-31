-- ============================================
-- Analytics Service: channel_daily_stats
-- ============================================
-- Daily snapshots of channel statistics
-- Used for tracking growth and reporting

CREATE TABLE `channel_daily_stats` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL COMMENT 'Reference to channels table',
  `platform_channel_id` varchar(64) NOT NULL COMMENT 'Platform-specific channel ID (for lookup)',
  `snapshot_date` date NOT NULL,
  `subscribers` bigint DEFAULT NULL,
  `views` bigint DEFAULT NULL,
  `videos` bigint DEFAULT NULL,
  `likes` bigint DEFAULT NULL,
  `comments` bigint DEFAULT NULL,
  `metadata` json DEFAULT NULL COMMENT 'Additional platform-specific stats',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_channel_date` (`channel_id`, `snapshot_date`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_snapshot_date` (`snapshot_date`),
  KEY `idx_platform_channel_id` (`platform_channel_id`),
  CONSTRAINT `fk_channel_daily_stats_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Daily channel statistics - Analytics Service';
