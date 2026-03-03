-- Migration 009: Add TOTP 2FA columns to platform_users
-- Idempotent: safe to run multiple times

SET @dbname = DATABASE();

-- Add totp_secret column (stores base32-encoded secret)
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'platform_users' AND COLUMN_NAME = 'totp_secret'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE platform_users ADD COLUMN totp_secret VARCHAR(64) DEFAULT NULL AFTER password_reset_token',
    'SELECT "totp_secret already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Add totp_enabled flag
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'platform_users' AND COLUMN_NAME = 'totp_enabled'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE platform_users ADD COLUMN totp_enabled TINYINT(1) NOT NULL DEFAULT 0 AFTER totp_secret',
    'SELECT "totp_enabled already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Add totp_backup_codes (JSON array of one-time recovery codes)
SET @col_exists = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = 'platform_users' AND COLUMN_NAME = 'totp_backup_codes'
);
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE platform_users ADD COLUMN totp_backup_codes JSON DEFAULT NULL AFTER totp_enabled',
    'SELECT "totp_backup_codes already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Record migration
INSERT IGNORE INTO platform_schema_migrations (version, description, applied_at, execution_ms)
VALUES ('009', 'Add TOTP 2FA columns to platform_users', NOW(), 0);
