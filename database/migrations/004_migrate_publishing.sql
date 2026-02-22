-- ============================================================================
-- Migration 004: Migrate Publishing Tasks
-- Content Fabric Database Refactoring
--
-- Migrates: tasks -> content_upload_queue_tasks (~5079 records)
--
-- Key transformations:
--   account_id   -> channel_id (same values, channels.id)
--   date_add     -> created_at
--   date_post    -> scheduled_at
--   date_done    -> completed_at
--   att_file_path-> source_file_path
--   cover        -> thumbnail_path
--   add_info     -> legacy_add_info (preserved as-is)
--   NEW: project_id (derived from channel), created_by, retry_count,
--        max_retries, error_code, upload_url, metadata
-- ============================================================================

SET @migration_version = '004_migrate_publishing';

-- Get default project and user
SET @default_project_id = (SELECT `id` FROM `platform_projects` WHERE `slug` = 'default' LIMIT 1);
SET @default_user_id = (SELECT MIN(`id`) FROM `platform_users`);

-- ============================================================================
-- Migrate tasks -> content_upload_queue_tasks
-- ============================================================================

INSERT INTO `content_upload_queue_tasks` (
    `id`, `project_id`, `channel_id`, `created_by`,
    `platform`, `media_type`, `status`,
    `source_file_path`, `thumbnail_path`,
    `title`, `description`, `keywords`, `post_comment`,
    `scheduled_at`, `completed_at`,
    `upload_id`, `error_message`,
    `legacy_add_info`,
    `created_at`
)
SELECT
    t.`id`,
    @default_project_id,
    t.`account_id`,                              -- account_id -> channel_id
    @default_user_id,                             -- created_by = default user
    COALESCE(t.`media_type`, 'youtube'),          -- platform
    CASE
        WHEN t.`media_type` IN ('short', 'shorts') THEN 'short'
        WHEN t.`media_type` IN ('reel', 'reels') THEN 'reel'
        WHEN t.`media_type` IN ('story', 'stories') THEN 'story'
        ELSE 'video'
    END,                                          -- media_type normalized
    t.`status`,
    t.`att_file_path`,                            -- -> source_file_path
    t.`cover`,                                    -- -> thumbnail_path
    COALESCE(t.`title`, '(untitled)'),
    t.`description`,
    t.`keywords`,
    t.`post_comment`,
    COALESCE(t.`date_post`, t.`date_add`, NOW()), -- -> scheduled_at
    t.`date_done`,                                -- -> completed_at
    t.`upload_id`,
    t.`error_message`,
    t.`add_info`,                                 -- -> legacy_add_info
    COALESCE(t.`date_add`, NOW())                 -- -> created_at
FROM `tasks` t
WHERE NOT EXISTS (
    SELECT 1 FROM `content_upload_queue_tasks` cuqt WHERE cuqt.`id` = t.`id`
)
-- Only migrate tasks whose channel exists in new schema
AND EXISTS (
    SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`
);

-- Log orphaned tasks (channel doesn't exist in new schema)
-- These are tasks with invalid account_id references
SELECT COUNT(*) AS orphaned_tasks_count
FROM `tasks` t
WHERE NOT EXISTS (
    SELECT 1 FROM `platform_channels` pc WHERE pc.`id` = t.`account_id`
);

-- ============================================================================
-- Record migration
-- ============================================================================

INSERT INTO `platform_schema_migrations` (`version`, `description`)
VALUES (@migration_version, 'Migrate tasks to content_upload_queue_tasks with column renames and project assignment');
