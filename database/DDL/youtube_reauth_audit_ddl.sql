CREATE TABLE `youtube_reauth_audit` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `channel_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `initiated_at` datetime NOT NULL,
  `completed_at` datetime DEFAULT NULL,
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  `metadata` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_channel_status` (`channel_name`,`status`),
  KEY `idx_initiated` (`initiated_at`),
  KEY `idx_completed` (`completed_at`),
  CONSTRAINT `youtube_reauth_audit_ibfk_1` FOREIGN KEY (`channel_name`) REFERENCES `youtube_channels` (`name`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3551 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci