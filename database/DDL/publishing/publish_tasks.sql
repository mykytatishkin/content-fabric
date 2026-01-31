-- ============================================
-- Publishing Service: publish_tasks
-- ============================================
-- Video publishing tasks for all platforms
-- Supports scheduling, retry logic, and status tracking

CREATE TABLE `publish_tasks` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL COMMENT 'Owner of this task',
  `channel_id` int unsigned NOT NULL COMMENT 'Target channel for publishing',
  `platform` varchar(50) NOT NULL DEFAULT 'youtube' COMMENT 'youtube, tiktok, instagram',
  `media_type` varchar(20) NOT NULL DEFAULT 'video' COMMENT 'video, short, reel, story',
  `status` tinyint NOT NULL DEFAULT 0 COMMENT '0=pending, 1=processing, 2=completed, 3=failed, 4=cancelled',
  
  -- File references
  `source_file_path` varchar(500) DEFAULT NULL COMMENT 'Path to source file (S3/local)',
  `thumbnail_path` varchar(500) DEFAULT NULL COMMENT 'Path to thumbnail image',
  
  -- Metadata
  `title` varchar(500) NOT NULL,
  `description` text,
  `keywords` text COMMENT 'Comma-separated tags',
  `post_comment` text COMMENT 'Comment to post after upload',
  `metadata` json DEFAULT NULL COMMENT 'Platform-specific metadata (privacy, category, etc.)',
  
  -- Scheduling
  `date_scheduled` datetime NOT NULL COMMENT 'Scheduled posting time',
  `date_started` datetime DEFAULT NULL COMMENT 'When processing started',
  `date_completed` datetime DEFAULT NULL COMMENT 'When task completed',
  
  -- Result tracking
  `upload_id` varchar(255) DEFAULT NULL COMMENT 'Platform video ID after upload',
  `upload_url` varchar(500) DEFAULT NULL COMMENT 'URL to uploaded video',
  `retry_count` int NOT NULL DEFAULT 0,
  `max_retries` int NOT NULL DEFAULT 3,
  `error_message` text,
  `error_code` varchar(100) DEFAULT NULL COMMENT 'Categorized error code',
  
  -- Legacy support
  `legacy_add_info` longtext COMMENT 'Legacy add_info field',
  
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_user_status` (`user_id`, `status`),
  KEY `idx_channel_status` (`channel_id`, `status`),
  KEY `idx_status_scheduled` (`status`, `date_scheduled`),
  KEY `idx_platform` (`platform`),
  KEY `idx_upload_id` (`upload_id`),
  CONSTRAINT `fk_publish_tasks_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_publish_tasks_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Publishing tasks - Publishing Service';
