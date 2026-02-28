-- Rollback 009: Remove TOTP 2FA columns from platform_users

ALTER TABLE platform_users
    DROP COLUMN IF EXISTS totp_backup_codes,
    DROP COLUMN IF EXISTS totp_enabled,
    DROP COLUMN IF EXISTS totp_secret;

DELETE FROM platform_schema_migrations WHERE version = '009';
