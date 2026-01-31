CREATE TABLE `youtube_channel_daily` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `yt_channel_id` int DEFAULT NULL,
  `channel_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `snapshot_date` date NOT NULL,
  `subscribers` bigint DEFAULT NULL,
  `views` bigint DEFAULT NULL,
  `videos` bigint DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_channel_date` (`channel_id`,`snapshot_date`)
) ENGINE=InnoDB AUTO_INCREMENT=2051 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci