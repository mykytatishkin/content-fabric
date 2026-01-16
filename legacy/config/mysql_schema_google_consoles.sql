-- SQL script to create google_consoles table and add console_id to youtube_channels
-- Run this if the migration script didn't work

-- Create google_consoles table
CREATE TABLE IF NOT EXISTS google_consoles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL COMMENT 'Human-readable name for the console',
    project_id VARCHAR(255) COMMENT 'Google Cloud Project ID (from credentials.json)',
    client_id TEXT NOT NULL COMMENT 'OAuth Client ID from Google Cloud Console',
    client_secret TEXT NOT NULL COMMENT 'OAuth Client Secret from Google Cloud Console',
    credentials_file VARCHAR(500) COMMENT 'Path to credentials.json file (optional)',
    redirect_uris JSON COMMENT 'OAuth redirect URIs from credentials.json',
    description TEXT COMMENT 'Optional description of the console/project',
    enabled BOOLEAN DEFAULT TRUE COMMENT 'Whether this console is active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_name (name),
    INDEX idx_project_id (project_id),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add console_id column to youtube_channels if it doesn't exist
-- Check if column exists first (MySQL doesn't support IF NOT EXISTS for ALTER TABLE)
SET @col_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'youtube_channels'
      AND COLUMN_NAME = 'console_id'
);

SET @sql = IF(@col_exists = 0,
    'ALTER TABLE youtube_channels ADD COLUMN console_id INT NULL COMMENT ''Reference to google_consoles.id'', ADD INDEX idx_console_id (console_id)',
    'SELECT ''Column console_id already exists'' AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add foreign key constraint if it doesn't exist
-- Note: This might fail if there are existing channels with invalid console_id values
-- In that case, you can add the constraint manually after cleaning up the data
SET @fk_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'youtube_channels'
      AND CONSTRAINT_NAME = 'fk_youtube_channels_console_id'
);

SET @sql_fk = IF(@fk_exists = 0,
    'ALTER TABLE youtube_channels ADD CONSTRAINT fk_youtube_channels_console_id FOREIGN KEY (console_id) REFERENCES google_consoles(id) ON DELETE SET NULL',
    'SELECT ''Foreign key constraint already exists'' AS message'
);

PREPARE stmt_fk FROM @sql_fk;
EXECUTE stmt_fk;
DEALLOCATE PREPARE stmt_fk;

-- Show result
SELECT 'Migration completed successfully!' AS status;
SELECT COUNT(*) AS google_consoles_count FROM google_consoles;
SELECT COUNT(*) AS channels_with_console FROM youtube_channels WHERE console_id IS NOT NULL;

