-- Reference DDL: platform_projects
-- NEW table (no legacy equivalent)
-- See: database/migrations/001_create_new_schema.sql

CREATE TABLE IF NOT EXISTS `platform_projects` (
  `id`                      INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `uuid`                    CHAR(36)        NOT NULL COMMENT 'Public-facing identifier',
  `owner_id`                INT UNSIGNED    NOT NULL COMMENT 'User who created the project',
  `name`                    VARCHAR(255)    NOT NULL,
  `slug`                    VARCHAR(100)    NOT NULL COMMENT 'URL-safe identifier',
  `description`             TEXT            DEFAULT NULL,
  `subscription_plan`       VARCHAR(50)     NOT NULL DEFAULT 'starter'
                            COMMENT 'starter, professional, business, enterprise',
  `subscription_expires_at` DATETIME        DEFAULT NULL,
  `settings`                JSON            DEFAULT NULL COMMENT 'Project-level settings',
  `status`                  SMALLINT        NOT NULL DEFAULT 10
                            COMMENT '0=archived, 9=suspended, 10=active',
  `created_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`              TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_pp_uuid`     (`uuid`),
  UNIQUE KEY `uniq_pp_slug`     (`slug`),
  KEY `idx_pp_owner`            (`owner_id`),
  KEY `idx_pp_status`           (`status`),
  CONSTRAINT `fk_pp_owner` FOREIGN KEY (`owner_id`) REFERENCES `platform_users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Project workspaces grouping all resources';
