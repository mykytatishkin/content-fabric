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

-- Grant permissions to application user (replace with your actual user)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON content_fabric.* TO 'content_fabric_user'@'%';
-- FLUSH PRIVILEGES;
