-- Reference DDL: platform_project_members
-- NEW table (no legacy equivalent)
-- See: database/migrations/001_create_new_schema.sql

CREATE TABLE IF NOT EXISTS `platform_project_members` (
  `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`    INT UNSIGNED    NOT NULL,
  `user_id`       INT UNSIGNED    NOT NULL,
  `role`          VARCHAR(50)     NOT NULL DEFAULT 'viewer'
                  COMMENT 'owner, admin, editor, viewer',
  `invited_by`    INT UNSIGNED    DEFAULT NULL,
  `invited_at`    TIMESTAMP       NULL DEFAULT NULL,
  `accepted_at`   TIMESTAMP       NULL DEFAULT NULL,
  `status`        VARCHAR(20)     NOT NULL DEFAULT 'active'
                  COMMENT 'pending, active, suspended, removed',
  `created_at`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_ppm_project_user`    (`project_id`, `user_id`),
  KEY `idx_ppm_user`                    (`user_id`),
  KEY `idx_ppm_role`                    (`role`),
  KEY `idx_ppm_status`                  (`status`),
  CONSTRAINT `fk_ppm_project`   FOREIGN KEY (`project_id`) REFERENCES `platform_projects` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ppm_user`      FOREIGN KEY (`user_id`)    REFERENCES `platform_users`    (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ppm_invited`   FOREIGN KEY (`invited_by`) REFERENCES `platform_users`    (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Project membership with RBAC roles';
