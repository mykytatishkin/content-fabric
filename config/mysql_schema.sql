-- MySQL Schema for Content Fabric YouTube Database
-- Migration from SQLite to MySQL

-- Create database (run this as root user)
-- CREATE DATABASE content_fabric CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE content_fabric;

-- Create youtube_channels table
CREATE TABLE IF NOT EXISTS youtube_channels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at DATETIME,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_name (name),
    INDEX idx_channel_id (channel_id),
    INDEX idx_enabled (enabled),
    INDEX idx_token_expires (token_expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create youtube_tokens table
CREATE TABLE IF NOT EXISTS youtube_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel_name VARCHAR(255) NOT NULL,
    token_type VARCHAR(100) NOT NULL,
    token_value TEXT NOT NULL,
    expires_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (channel_name) REFERENCES youtube_channels(name) ON DELETE CASCADE,
    INDEX idx_channel_name (channel_name),
    INDEX idx_token_type (token_type),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create tasks table for scheduled posting
CREATE TABLE IF NOT EXISTS tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    media_type VARCHAR(50) NOT NULL DEFAULT 'youtube',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '0=pending, 1=completed, 2=failed, 3=processing',
    date_add TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    att_file_path TEXT NOT NULL COMMENT 'Path to video file',
    cover TEXT COMMENT 'Path to thumbnail/cover image',
    title VARCHAR(500) NOT NULL COMMENT 'Video title',
    description TEXT COMMENT 'Video description',
    keywords TEXT COMMENT 'Keywords/hashtags',
    post_comment TEXT COMMENT 'Comment to post after upload',
    add_info JSON COMMENT 'Additional information in JSON format',
    date_post DATETIME NOT NULL COMMENT 'Scheduled posting time',
    date_done DATETIME COMMENT 'Actual execution time',
    upload_id VARCHAR(255) COMMENT 'Video ID from platform after upload',
    
    FOREIGN KEY (account_id) REFERENCES youtube_channels(id) ON DELETE CASCADE,
    INDEX idx_account_id (account_id),
    INDEX idx_media_type (media_type),
    INDEX idx_status (status),
    INDEX idx_date_post (date_post),
    INDEX idx_status_date_post (status, date_post),
    INDEX idx_upload_id (upload_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create indexes for better performance
CREATE INDEX idx_youtube_channels_enabled_created ON youtube_channels(enabled, created_at);
CREATE INDEX idx_youtube_tokens_channel_expires ON youtube_tokens(channel_name, expires_at);

-- Add some useful views for monitoring
CREATE VIEW active_channels AS
SELECT 
    id,
    name,
    channel_id,
    enabled,
    CASE 
        WHEN token_expires_at IS NULL THEN 'No Token'
        WHEN token_expires_at < NOW() THEN 'Expired'
        ELSE 'Valid'
    END as token_status,
    token_expires_at,
    created_at,
    updated_at
FROM youtube_channels 
WHERE enabled = TRUE;

CREATE VIEW expired_tokens AS
SELECT 
    c.id,
    c.name,
    c.channel_id,
    c.token_expires_at,
    c.updated_at
FROM youtube_channels c
WHERE c.enabled = TRUE 
  AND (c.token_expires_at IS NULL OR c.token_expires_at < NOW());

CREATE VIEW pending_tasks AS
SELECT 
    t.id,
    t.account_id,
    c.name as account_name,
    t.media_type,
    t.title,
    t.date_post,
    t.status,
    CASE 
        WHEN t.status = 0 THEN 'Pending'
        WHEN t.status = 1 THEN 'Completed'
        WHEN t.status = 2 THEN 'Failed'
        WHEN t.status = 3 THEN 'Processing'
        ELSE 'Unknown'
    END as status_text,
    t.date_add,
    t.retry_count
FROM tasks t
LEFT JOIN youtube_channels c ON t.account_id = c.id
WHERE t.status = 0 AND t.date_post <= NOW()
ORDER BY t.date_post ASC;

-- Grant permissions to application user (replace with your actual user)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON content_fabric.* TO 'content_fabric_user'@'%';
-- FLUSH PRIVILEGES;
