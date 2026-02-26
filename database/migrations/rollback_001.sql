-- ============================================================================
-- Rollback 001: Drop all new tables
-- Reverses: 001_create_new_schema.sql
-- Safe to run: legacy tables are untouched
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `live_stream_configurations`;
DROP TABLE IF EXISTS `live_streaming_accounts`;
DROP TABLE IF EXISTS `channel_reauth_audit_logs`;
DROP TABLE IF EXISTS `channel_daily_statistics`;
DROP TABLE IF EXISTS `content_upload_queue_tasks`;
DROP TABLE IF EXISTS `platform_channel_login_credentials`;
DROP TABLE IF EXISTS `platform_channel_tokens`;
DROP TABLE IF EXISTS `platform_channels`;
DROP TABLE IF EXISTS `platform_oauth_credentials`;
DROP TABLE IF EXISTS `platform_project_members`;
DROP TABLE IF EXISTS `platform_projects`;
DROP TABLE IF EXISTS `platform_users`;
DROP TABLE IF EXISTS `platform_schema_migrations`;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Rollback 001 complete: all new tables dropped, legacy tables intact.' AS result;
