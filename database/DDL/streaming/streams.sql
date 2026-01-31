-- ============================================
-- Streaming Service: streams
-- ============================================
-- Live stream configurations
-- Manages broadcast settings and RTMP keys

CREATE TABLE `streams` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL COMMENT 'Owner of this stream',
  `streaming_account_id` int unsigned DEFAULT NULL COMMENT 'Reference to streaming_accounts',
  `channel_id` int unsigned DEFAULT NULL COMMENT 'Reference to channels (optional)',
  
  -- Stream identification
  `name` varchar(120) NOT NULL COMMENT 'Stream name for UI',
  `service_name` varchar(160) NOT NULL COMMENT 'Systemd service name',
  `workdir` varchar(255) NOT NULL COMMENT 'Working directory for stream files',
  
  -- RTMP settings
  `rtmp_host` varchar(255) DEFAULT NULL,
  `rtmp_base` varchar(255) DEFAULT NULL,
  `stream_key` varchar(255) DEFAULT NULL,
  `duration_sec` int NOT NULL DEFAULT 42900 COMMENT 'Stream duration in seconds',
  
  -- Platform-specific IDs
  `platform_broadcast_id` varchar(64) DEFAULT NULL COMMENT 'Platform liveBroadcast ID',
  `platform_video_id` varchar(64) DEFAULT NULL COMMENT 'Platform video ID',
  `platform_stream_id` varchar(64) DEFAULT NULL COMMENT 'Platform stream ID',
  `platform_stream_key` varchar(128) DEFAULT NULL COMMENT 'Platform-generated stream key',
  
  -- Stream metadata
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `tags` text COMMENT 'Comma-separated',
  `thumbnail_path` varchar(255) DEFAULT NULL,
  
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `notes` text,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_service_name` (`service_name`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_streaming_account_id` (`streaming_account_id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_enabled` (`enabled`),
  CONSTRAINT `fk_streams_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_streams_streaming_account` FOREIGN KEY (`streaming_account_id`) REFERENCES `streaming_accounts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_streams_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Live stream configurations - Streaming Service';
