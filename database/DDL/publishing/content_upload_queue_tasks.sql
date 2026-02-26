-- Reference DDL: content_upload_queue_tasks
-- Replaces: tasks (legacy)
-- See: database/migrations/001_create_new_schema.sql

CREATE TABLE IF NOT EXISTS `content_upload_queue_tasks` (
  `id`                INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `project_id`        INT UNSIGNED    NOT NULL,
  `channel_id`        INT UNSIGNED    NOT NULL,
  `created_by`        INT UNSIGNED    DEFAULT NULL COMMENT 'User who created the task',
  `platform`          VARCHAR(50)     NOT NULL DEFAULT 'youtube',
  `media_type`        VARCHAR(20)     NOT NULL DEFAULT 'video'
                      COMMENT 'video, short, reel, story',
  `status`            TINYINT         NOT NULL DEFAULT 0
                      COMMENT '0=pending, 1=completed, 2=failed, 3=processing, 4=cancelled',
  `source_file_path`  VARCHAR(500)    DEFAULT NULL,
  `thumbnail_path`    VARCHAR(500)    DEFAULT NULL,
  `title`             VARCHAR(500)    NOT NULL,
  `description`       TEXT            DEFAULT NULL,
  `keywords`          TEXT            DEFAULT NULL COMMENT 'Comma-separated tags',
  `post_comment`      TEXT            DEFAULT NULL COMMENT 'Comment to post after upload',
  `metadata`          JSON            DEFAULT NULL
                      COMMENT 'Platform-specific: privacy, category, etc.',
  `scheduled_at`      DATETIME        NOT NULL COMMENT 'When to publish',
  `started_at`        DATETIME        DEFAULT NULL COMMENT 'When processing began',
  `completed_at`      DATETIME        DEFAULT NULL COMMENT 'When task finished',
  `upload_id`         VARCHAR(255)    DEFAULT NULL COMMENT 'Platform video ID after upload',
  `upload_url`        VARCHAR(500)    DEFAULT NULL COMMENT 'URL to published content',
  `retry_count`       INT             NOT NULL DEFAULT 0,
  `max_retries`       INT             NOT NULL DEFAULT 3,
  `error_message`     TEXT            DEFAULT NULL,
  `error_code`        VARCHAR(100)    DEFAULT NULL COMMENT 'Categorized error code',
  `legacy_add_info`   LONGTEXT        DEFAULT NULL COMMENT 'Preserved legacy add_info JSON',
  `created_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cuqt_project`            (`project_id`),
  KEY `idx_cuqt_channel`            (`channel_id`),
  KEY `idx_cuqt_created_by`         (`created_by`),
  KEY `idx_cuqt_project_status`     (`project_id`, `status`),
  KEY `idx_cuqt_channel_status`     (`channel_id`, `status`),
  KEY `idx_cuqt_status_scheduled`   (`status`, `scheduled_at`),
  KEY `idx_cuqt_platform`           (`platform`),
  KEY `idx_cuqt_upload_id`          (`upload_id`),
  CONSTRAINT `fk_cuqt_project`      FOREIGN KEY (`project_id`)  REFERENCES `platform_projects`  (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cuqt_channel`      FOREIGN KEY (`channel_id`)  REFERENCES `platform_channels`  (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_cuqt_created_by`   FOREIGN KEY (`created_by`)  REFERENCES `platform_users`     (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Content publishing task queue';
