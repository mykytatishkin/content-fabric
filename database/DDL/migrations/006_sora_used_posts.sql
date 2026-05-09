-- 006_sora_used_posts.sql
-- Tracks Sora AI feed posts that were already downloaded/queued.
-- Replaces Yii's used_posts.txt file from SoraController.actionGet_video.
-- Apply on prod: mysql -u content_fabric_user -pmysqlpassword content_fabric < /path/to/006_sora_used_posts.sql

CREATE TABLE IF NOT EXISTS sora_used_posts (
  post_id VARCHAR(255) NOT NULL PRIMARY KEY,
  fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  channel_id INT UNSIGNED NULL,
  INDEX idx_fetched_at (fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO platform_schema_migrations (version, applied_at)
VALUES ('006_sora_used_posts', NOW());
