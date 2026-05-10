-- 007_news_processed_urls.sql
-- Tracks news RSS items already processed, so the news worker doesn't
-- re-publish them. Replaces Yii's rbc_used_links.txt file from
-- NewsController.actionRbcFirstNews.
-- Apply on prod: mysql -u content_fabric_user -pmysqlpassword content_fabric < /path/to/007_news_processed_urls.sql

CREATE TABLE IF NOT EXISTS news_processed_urls (
  link VARCHAR(1000) NOT NULL,
  source VARCHAR(50) NOT NULL DEFAULT 'rbc',
  processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (link(255)),
  INDEX idx_source (source),
  INDEX idx_processed_at (processed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO platform_schema_migrations (version, applied_at)
VALUES ('007_news_processed_urls', NOW());
