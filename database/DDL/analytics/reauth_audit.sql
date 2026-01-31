-- ============================================
-- Analytics Service: reauth_audit
-- ============================================
-- Audit log for channel reauthorization attempts
-- Tracks success/failure of automated OAuth refresh

CREATE TABLE `reauth_audit` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `channel_id` int unsigned NOT NULL COMMENT 'Reference to channels',
  `initiated_at` datetime NOT NULL,
  `completed_at` datetime DEFAULT NULL,
  `status` varchar(32) NOT NULL COMMENT 'started, success, failed, timeout',
  `trigger_reason` varchar(100) DEFAULT NULL COMMENT 'token_expired, manual, error_recovery',
  `error_message` text,
  `error_code` varchar(100) DEFAULT NULL,
  `metadata` json DEFAULT NULL COMMENT 'Additional context (IP, user agent, etc.)',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_channel_id` (`channel_id`),
  KEY `idx_channel_status` (`channel_id`, `status`),
  KEY `idx_initiated` (`initiated_at`),
  KEY `idx_completed` (`completed_at`),
  KEY `idx_status` (`status`),
  CONSTRAINT `fk_reauth_audit_channel` FOREIGN KEY (`channel_id`) REFERENCES `channels` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Reauthorization audit log - Analytics Service';
