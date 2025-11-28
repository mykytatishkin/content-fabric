-- MySQL Schema for Content Fabric YouTube Database

-- Create database (run this as root user)
-- CREATE DATABASE content_fabric CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE content_fabric;

-- Create google_consoles table for storing Google Cloud Console credentials
CREATE TABLE IF NOT EXISTS google_consoles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL COMMENT 'Human-readable name for the console (used as unique identifier)',
    client_id TEXT NOT NULL COMMENT 'OAuth Client ID from Google Cloud Console',
    client_secret TEXT NOT NULL COMMENT 'OAuth Client Secret from Google Cloud Console',
    credentials_file CHAR(500) COMMENT 'Path to credentials.json file (optional)',
    description TEXT COMMENT 'Optional description of the console/project',
    enabled TINYINT(1) DEFAULT 1 COMMENT 'Whether this console is active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_name (name),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create youtube_channels table
CREATE TABLE IF NOT EXISTS youtube_channels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    channel_id VARCHAR(255) NOT NULL,
    console_name VARCHAR(255) COMMENT 'Reference to google_consoles.name (nullable for backward compatibility)',
    client_id TEXT COMMENT 'Deprecated: use google_consoles.client_id instead (kept for backward compatibility)',
    client_secret TEXT COMMENT 'Deprecated: use google_consoles.client_secret instead (kept for backward compatibility)',
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at DATETIME,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (console_name) REFERENCES google_consoles(name) ON DELETE SET NULL,
    INDEX idx_name (name),
    INDEX idx_channel_id (channel_id),
    INDEX idx_console_name (console_name),
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

-- Credentials table for automated OAuth re-authentication
CREATE TABLE IF NOT EXISTS youtube_account_credentials (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel_name VARCHAR(255) NOT NULL,
    login_email VARCHAR(320) NOT NULL,
    login_password TEXT NOT NULL COMMENT 'Stored in raw form; ensure server access is restricted',
    totp_secret VARCHAR(64),
    backup_codes JSON,
    proxy_host VARCHAR(255),
    proxy_port INT,
    proxy_username VARCHAR(255),
    proxy_password VARCHAR(255),
    profile_path VARCHAR(500),
    user_agent VARCHAR(500),
    last_success_at DATETIME,
    last_attempt_at DATETIME,
    last_error TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (channel_name) REFERENCES youtube_channels(name) ON DELETE CASCADE,
    UNIQUE KEY idx_channel_unique (channel_name),
    INDEX idx_login_email (login_email),
    INDEX idx_enabled (enabled),
    INDEX idx_last_success (last_success_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Audit table for tracking automated re-auth attempts
CREATE TABLE IF NOT EXISTS youtube_reauth_audit (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    channel_name VARCHAR(255) NOT NULL,
    initiated_at DATETIME NOT NULL,
    completed_at DATETIME,
    status VARCHAR(32) NOT NULL,
    error_message TEXT,
    metadata JSON,

    FOREIGN KEY (channel_name) REFERENCES youtube_channels(name) ON DELETE CASCADE,
    INDEX idx_channel_status (channel_name, status),
    INDEX idx_initiated (initiated_at),
    INDEX idx_completed (completed_at)
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
