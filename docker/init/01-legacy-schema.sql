-- ============================================================================
-- Legacy Schema for Local Development
-- Creates the legacy tables and inserts sample data
-- to test migration scripts 001-007
-- ============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- Legacy: user
-- ============================================================================
CREATE TABLE IF NOT EXISTS `user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `auth_key` varchar(32) COLLATE utf8mb3_unicode_ci NOT NULL,
  `password_hash` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `password_reset_token` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb3_unicode_ci NOT NULL,
  `status` smallint NOT NULL DEFAULT '10',
  `created_at` int NOT NULL,
  `updated_at` int NOT NULL,
  `verification_token` varchar(255) COLLATE utf8mb3_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `password_reset_token` (`password_reset_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_unicode_ci;

INSERT INTO `user` (`id`, `username`, `auth_key`, `password_hash`, `email`, `status`, `created_at`, `updated_at`)
VALUES (1, 'admin', 'test_auth_key_32_chars_here_ok_', '$2y$13$testhash', 'admin@test.local', 10, 1696300800, 1696300800);

-- ============================================================================
-- Legacy: google_consoles
-- ============================================================================
CREATE TABLE IF NOT EXISTS `google_consoles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `client_id` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `client_secret` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `credentials_file` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `enabled` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `project_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `redirect_uris` json DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_name` (`name`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_project_id` (`project_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `google_consoles` (`id`, `name`, `client_id`, `client_secret`, `project_id`, `description`, `enabled`)
VALUES
  (1, 'Console-Alpha', 'client_id_alpha', 'client_secret_alpha', 'proj-alpha', 'Test console 1', 1),
  (2, 'Console-Beta', 'client_id_beta', 'client_secret_beta', 'proj-beta', 'Test console 2', 1),
  (3, 'Console-Gamma', 'client_id_gamma', 'client_secret_gamma', 'proj-gamma', 'Disabled console', 0);

-- ============================================================================
-- Legacy: youtube_channels
-- ============================================================================
CREATE TABLE IF NOT EXISTS `youtube_channels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `channel_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `console_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `access_token` text COLLATE utf8mb4_unicode_ci,
  `refresh_token` text COLLATE utf8mb4_unicode_ci,
  `token_expires_at` datetime DEFAULT NULL,
  `enabled` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `stat` tinyint(1) NOT NULL DEFAULT '0',
  `add_info` text COLLATE utf8mb4_unicode_ci,
  `console_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_youtube_channels_enabled_created` (`enabled`,`created_at`),
  KEY `idx_console_id` (`console_id`),
  KEY `idx_console_name` (`console_name`),
  CONSTRAINT `fk_youtube_channels_console_id` FOREIGN KEY (`console_id`) REFERENCES `google_consoles` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_youtube_channels_console_name` FOREIGN KEY (`console_name`) REFERENCES `google_consoles` (`name`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `youtube_channels` (`id`, `name`, `channel_id`, `console_name`, `console_id`, `access_token`, `refresh_token`, `token_expires_at`, `enabled`, `stat`)
VALUES
  (1, 'TestChannel-1', 'UC_test_channel_1', 'Console-Alpha', 1, 'access_tok_1', 'refresh_tok_1', '2026-03-01 00:00:00', 1, 0),
  (2, 'TestChannel-2', 'UC_test_channel_2', 'Console-Beta', 2, 'access_tok_2', 'refresh_tok_2', '2026-02-15 00:00:00', 1, 0),
  (3, 'TestChannel-Disabled', 'UC_test_channel_3', NULL, NULL, NULL, NULL, NULL, 0, 0);

-- ============================================================================
-- Legacy: youtube_tokens (unused in prod, but test migration)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `youtube_tokens` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `token_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `token_value` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_youtube_tokens_channel_expires` (`channel_name`,`expires_at`),
  CONSTRAINT `youtube_tokens_ibfk_1` FOREIGN KEY (`channel_name`) REFERENCES `youtube_channels` (`name`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `youtube_tokens` (`id`, `channel_name`, `token_type`, `token_value`, `expires_at`)
VALUES
  (1, 'TestChannel-1', 'access_token', 'old_access_token', '2025-01-01 00:00:00'),
  (2, 'TestChannel-1', 'refresh_token', 'old_refresh_token', NULL);

-- ============================================================================
-- Legacy: youtube_account_credentials
-- ============================================================================
CREATE TABLE IF NOT EXISTS `youtube_account_credentials` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `login_email` varchar(320) COLLATE utf8mb4_unicode_ci NOT NULL,
  `login_password` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `totp_secret` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `backup_codes` json DEFAULT NULL,
  `proxy_host` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `proxy_port` int DEFAULT NULL,
  `proxy_username` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `proxy_password` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `profile_path` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_agent` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_success_at` datetime DEFAULT NULL,
  `last_attempt_at` datetime DEFAULT NULL,
  `last_error` text COLLATE utf8mb4_unicode_ci,
  `enabled` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_channel_unique` (`channel_name`),
  KEY `idx_login_email` (`login_email`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_last_success` (`last_success_at`),
  CONSTRAINT `youtube_account_credentials_ibfk_1` FOREIGN KEY (`channel_name`) REFERENCES `youtube_channels` (`name`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `youtube_account_credentials` (`id`, `channel_name`, `login_email`, `login_password`, `totp_secret`, `proxy_host`, `proxy_port`, `enabled`)
VALUES
  (1, 'TestChannel-1', 'test1@gmail.com', 'encrypted_pass_1', 'TOTP_SECRET_1', '192.168.1.1', 8080, 1),
  (2, 'TestChannel-2', 'test2@gmail.com', 'encrypted_pass_2', NULL, NULL, NULL, 1);

-- ============================================================================
-- Legacy: youtube_reauth_audit
-- ============================================================================
CREATE TABLE IF NOT EXISTS `youtube_reauth_audit` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `youtube_reauth_audit` (`id`, `channel_name`, `initiated_at`, `completed_at`, `status`, `error_message`)
VALUES
  (1, 'TestChannel-1', '2025-12-01 10:00:00', '2025-12-01 10:05:00', 'success', NULL),
  (2, 'TestChannel-1', '2025-12-15 14:00:00', '2025-12-15 14:03:00', 'failed', 'CAPTCHA detected'),
  (3, 'TestChannel-2', '2026-01-10 09:00:00', '2026-01-10 09:02:00', 'success', NULL);

-- ============================================================================
-- Legacy: tasks
-- ============================================================================
CREATE TABLE IF NOT EXISTS `tasks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `account_id` int DEFAULT NULL,
  `media_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `status` tinyint(1) DEFAULT '0',
  `date_add` datetime DEFAULT NULL,
  `att_file_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cover` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `title` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `keywords` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `post_comment` text COLLATE utf8mb4_unicode_ci,
  `add_info` longtext COLLATE utf8mb4_unicode_ci,
  `date_post` datetime DEFAULT NULL,
  `date_done` datetime DEFAULT NULL,
  `upload_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `idx_upload_id` (`upload_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `tasks` (`id`, `account_id`, `media_type`, `status`, `date_add`, `att_file_path`, `title`, `description`, `date_post`, `date_done`, `upload_id`, `error_message`)
VALUES
  (1, 1, 'youtube', 1, '2025-11-01 12:00:00', '/videos/test1.mp4', 'Test Video 1', 'Description 1', '2025-11-01 18:00:00', '2025-11-01 18:05:00', 'yt_video_id_1', NULL),
  (2, 1, 'youtube', 0, '2025-12-01 12:00:00', '/videos/test2.mp4', 'Pending Video', 'Pending desc', '2026-03-01 12:00:00', NULL, NULL, NULL),
  (3, 2, 'youtube', 2, '2025-12-15 08:00:00', '/videos/test3.mp4', 'Failed Video', 'Failed desc', '2025-12-15 12:00:00', '2025-12-15 12:10:00', NULL, 'Token expired'),
  (4, 99, 'youtube', 0, '2026-01-01 00:00:00', '/videos/orphan.mp4', 'Orphaned Task', 'No channel', '2026-04-01 00:00:00', NULL, NULL, NULL);

-- ============================================================================
-- Legacy: youtube_channel_daily
-- ============================================================================
CREATE TABLE IF NOT EXISTS `youtube_channel_daily` (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `youtube_channel_daily` (`id`, `yt_channel_id`, `channel_id`, `snapshot_date`, `subscribers`, `views`, `videos`)
VALUES
  (1, 1, 'UC_test_channel_1', '2025-12-01', 1000, 50000, 25),
  (2, 1, 'UC_test_channel_1', '2025-12-02', 1010, 51000, 25),
  (3, 2, 'UC_test_channel_2', '2025-12-01', 500, 20000, 10);

-- ============================================================================
-- Legacy: youtube_account (streaming)
-- ============================================================================
CREATE TABLE IF NOT EXISTS `youtube_account` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `client_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `client_secret` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `access_token` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `refresh_token` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `token_expires` int unsigned DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_token_expires` (`token_expires`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `youtube_account` (`id`, `name`, `client_id`, `client_secret`, `access_token`, `refresh_token`, `token_expires`)
VALUES
  (1, 'Stream Account 1', 'stream_client_1', 'stream_secret_1', 'stream_access_1', 'stream_refresh_1', 1772000000);

-- ============================================================================
-- Legacy: stream
-- ============================================================================
CREATE TABLE IF NOT EXISTS `stream` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(120) NOT NULL,
  `service_name` varchar(160) NOT NULL,
  `workdir` varchar(255) NOT NULL,
  `channel_name` varchar(160) DEFAULT NULL,
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `notes` text,
  `created_at` int NOT NULL,
  `updated_at` int NOT NULL,
  `stream_key` varchar(255) DEFAULT NULL,
  `duration_sec` int DEFAULT '42900',
  `rtmp_base` varchar(255) DEFAULT NULL,
  `rtmp_host` varchar(255) DEFAULT NULL,
  `youtube_broadcast_id` varchar(64) DEFAULT NULL,
  `youtube_video_id` varchar(64) DEFAULT NULL,
  `yt_title` varchar(255) DEFAULT NULL,
  `yt_description` text,
  `yt_tags` text,
  `yt_thumbnail` varchar(255) DEFAULT NULL,
  `youtube_account_id` int unsigned DEFAULT NULL,
  `youtube_stream_id` varchar(64) DEFAULT NULL,
  `youtube_stream_key` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_service` (`service_name`),
  KEY `idx_stream_yta` (`youtube_account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO `stream` (`id`, `name`, `service_name`, `workdir`, `channel_name`, `enabled`, `created_at`, `updated_at`, `yt_title`, `youtube_account_id`, `rtmp_host`, `rtmp_base`)
VALUES
  (1, 'Test Stream', 'stream-test-1', '/opt/streams/test1', 'TestChannel-1', 1, 1700000000, 1700000000, 'Live Test', 1, 'rtmp://a.rtmp.youtube.com', '/live2');

-- ============================================================================
-- Legacy: migration tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS `migration` (
  `version` varchar(180) COLLATE utf8mb4_unicode_ci NOT NULL,
  `apply_time` int DEFAULT NULL,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Legacy schema + test data loaded successfully' AS status;
