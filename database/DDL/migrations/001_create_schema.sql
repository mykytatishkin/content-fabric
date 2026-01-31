-- ============================================
-- Migration 001: Create New Schema Structure
-- ============================================
-- This migration creates all new tables for the microservice architecture
-- Run this BEFORE the data migration script
--
-- IMPORTANT: Run in a transaction or have backups ready
-- ============================================

-- Disable foreign key checks during migration
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================
-- AUTH SERVICE
-- ============================================

CREATE TABLE IF NOT EXISTS `users` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `uuid` char(36) NOT NULL,
  `username` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) DEFAULT NULL,
  `auth_key` varchar(32) NOT NULL,
  `password_reset_token` varchar(255) DEFAULT NULL,
  `verification_token` varchar(255) DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `avatar_url` text DEFAULT NULL,
  `status` smallint NOT NULL DEFAULT 10,
  `subscription_plan` varchar(50) NOT NULL DEFAULT 'starter',
  `subscription_expires_at` datetime DEFAULT NULL,
  `timezone` varchar(64) DEFAULT 'UTC',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_uuid` (`uuid`),
  UNIQUE KEY `uniq_username` (`username`),
  UNIQUE KEY `uniq_email` (`email`),
  UNIQUE KEY `uniq_password_reset_token` (`password_reset_token`),
  KEY `idx_status` (`status`),
  KEY `idx_subscription` (`subscription_plan`, `subscription_expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- CHANNEL SERVICE
-- ============================================

CREATE TABLE IF NOT EXISTS `oauth_consoles` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `platform` varchar(50) NOT NULL DEFAULT 'google',
  `name` varchar(255) NOT NULL,
  `project_id` varchar(255) DEFAULT NULL,
  `client_id` text NOT NULL,
  `client_secret` text NOT NULL,
  `redirect_uris` json DEFAULT NULL,
  `credentials_file` varchar(500) DEFAULT NULL,
  `description` text,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_platform_name` (`user_id`, `platform`, `name`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_platform` (`platform`),
  KEY `idx_enabled` (`enabled`),
  CONSTRAINT `fk_oauth_consoles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `channels` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `platform` varchar(50) NOT NULL DEFAULT 'youtube',
  `name` varchar(255) NOT NULL,
  `platform_channel_id` varchar(255) NOT NULL,
  `console_id` int unsigned DEFAULT NULL,
  `access_token` text,
  `refresh_token` text,
  `token_expires_at` datetime DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `stat` tinyint(1) NOT NULL DEFAULT 0,
  `metadata` json DEFAULT NULL,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `channel_tokens` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL,
  `token_type` varchar(100) NOT NULL,
  `token_value` text NOT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_channel_expires` (`channel_id`, `expires_at`),
  KEY `idx_token_type` (`token_type`),
  CONSTRAINT `fk_channel_tokens_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `channel_credentials` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL,
  `login_email` varchar(320) NOT NULL,
  `login_password` text NOT NULL,
  `totp_secret` varchar(64) DEFAULT NULL,
  `backup_codes` json DEFAULT NULL,
  `proxy_host` varchar(255) DEFAULT NULL,
  `proxy_port` int DEFAULT NULL,
  `proxy_username` varchar(255) DEFAULT NULL,
  `proxy_password` varchar(255) DEFAULT NULL,
  `profile_path` varchar(500) DEFAULT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  `last_success_at` datetime DEFAULT NULL,
  `last_attempt_at` datetime DEFAULT NULL,
  `last_error` text,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_channel_id` (`channel_id`),
  KEY `idx_login_email` (`login_email`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_last_success` (`last_success_at`),
  CONSTRAINT `fk_channel_credentials_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- PUBLISHING SERVICE
-- ============================================

CREATE TABLE IF NOT EXISTS `publish_tasks` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `channel_id` int unsigned NOT NULL,
  `platform` varchar(50) NOT NULL DEFAULT 'youtube',
  `media_type` varchar(20) NOT NULL DEFAULT 'video',
  `status` tinyint NOT NULL DEFAULT 0,
  `source_file_path` varchar(500) DEFAULT NULL,
  `thumbnail_path` varchar(500) DEFAULT NULL,
  `title` varchar(500) NOT NULL,
  `description` text,
  `keywords` text,
  `post_comment` text,
  `metadata` json DEFAULT NULL,
  `date_scheduled` datetime NOT NULL,
  `date_started` datetime DEFAULT NULL,
  `date_completed` datetime DEFAULT NULL,
  `upload_id` varchar(255) DEFAULT NULL,
  `upload_url` varchar(500) DEFAULT NULL,
  `retry_count` int NOT NULL DEFAULT 0,
  `max_retries` int NOT NULL DEFAULT 3,
  `error_message` text,
  `error_code` varchar(100) DEFAULT NULL,
  `legacy_add_info` longtext,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- ANALYTICS SERVICE
-- ============================================

CREATE TABLE IF NOT EXISTS `channel_daily_stats` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL,
  `platform_channel_id` varchar(64) NOT NULL,
  `snapshot_date` date NOT NULL,
  `subscribers` bigint DEFAULT NULL,
  `views` bigint DEFAULT NULL,
  `videos` bigint DEFAULT NULL,
  `likes` bigint DEFAULT NULL,
  `comments` bigint DEFAULT NULL,
  `metadata` json DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_channel_date` (`channel_id`, `snapshot_date`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_snapshot_date` (`snapshot_date`),
  KEY `idx_platform_channel_id` (`platform_channel_id`),
  CONSTRAINT `fk_channel_daily_stats_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `reauth_audit` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL,
  `initiated_at` datetime NOT NULL,
  `completed_at` datetime DEFAULT NULL,
  `status` varchar(32) NOT NULL,
  `trigger_reason` varchar(100) DEFAULT NULL,
  `error_message` text,
  `error_code` varchar(100) DEFAULT NULL,
  `metadata` json DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_channel_status` (`channel_id`, `status`),
  KEY `idx_initiated` (`initiated_at`),
  KEY `idx_completed` (`completed_at`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_reauth_audit_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================
-- STREAMING SERVICE
-- ============================================

CREATE TABLE IF NOT EXISTS `streaming_accounts` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `platform` varchar(50) NOT NULL DEFAULT 'youtube',
  `name` varchar(255) NOT NULL,
  `client_id` varchar(255) NOT NULL,
  `client_secret` varchar(255) NOT NULL,
  `access_token` text NOT NULL,
  `refresh_token` text NOT NULL,
  `token_expires_at` int unsigned DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_platform_name` (`user_id`, `platform`, `name`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_platform` (`platform`),
  KEY `idx_token_expires` (`token_expires_at`),
  CONSTRAINT `fk_streaming_accounts_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `streams` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int unsigned NOT NULL,
  `streaming_account_id` int unsigned DEFAULT NULL,
  `channel_id` int unsigned DEFAULT NULL,
  `name` varchar(120) NOT NULL,
  `service_name` varchar(160) NOT NULL,
  `workdir` varchar(255) NOT NULL,
  `rtmp_host` varchar(255) DEFAULT NULL,
  `rtmp_base` varchar(255) DEFAULT NULL,
  `stream_key` varchar(255) DEFAULT NULL,
  `duration_sec` int NOT NULL DEFAULT 42900,
  `platform_broadcast_id` varchar(64) DEFAULT NULL,
  `platform_video_id` varchar(64) DEFAULT NULL,
  `platform_stream_id` varchar(64) DEFAULT NULL,
  `platform_stream_key` varchar(128) DEFAULT NULL,
  `title` varchar(255) DEFAULT NULL,
  `description` text,
  `tags` text,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- Log migration
INSERT INTO migration (version, apply_time) VALUES ('001_create_schema', UNIX_TIMESTAMP())
ON DUPLICATE KEY UPDATE apply_time = UNIX_TIMESTAMP();

SELECT 'Migration 001: Schema created successfully' AS status;
