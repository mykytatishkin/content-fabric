-- Add user_id column for multi-tenancy (nullable for backward compatibility)
-- Run: mysql -u user -p content_fabric < migrations/add_user_id_to_youtube_channels.sql
-- Note: Run once. If column exists, ignore the error.

ALTER TABLE youtube_channels
ADD COLUMN user_id VARCHAR(36) NULL
COMMENT 'UUID of user/tenant (nullable until auth service integrated)'
AFTER enabled;

CREATE INDEX idx_user_id ON youtube_channels(user_id);
