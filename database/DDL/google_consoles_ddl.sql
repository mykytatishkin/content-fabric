CREATE TABLE `google_consoles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Human-readable name for the console',
  `client_id` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'OAuth Client ID from Google Cloud Console',
  `client_secret` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'OAuth Client Secret from Google Cloud Console',
  `credentials_file` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Path to credentials.json file (optional)',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT 'Optional description of the console/project',
  `enabled` tinyint(1) DEFAULT '1' COMMENT 'Whether this console is active',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `project_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Google Cloud Project ID (from credentials.json)',
  `redirect_uris` json DEFAULT NULL COMMENT 'OAuth redirect URIs from credentials.json',
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  KEY `idx_name` (`name`),
  KEY `idx_enabled` (`enabled`),
  KEY `idx_project_id` (`project_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci