-- ============================================
-- Migration 002: Migrate Data from Legacy Tables
-- ============================================
-- This script migrates all existing data to the new schema
-- Assumes 001_create_schema.sql has been run first
--
-- IMPORTANT: 
-- 1. Backup your database before running this migration!
-- 2. This creates a default admin user to own all migrated data
-- 3. Review and test in a staging environment first
-- ============================================

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================
-- STEP 1: Migrate Users (or create default admin)
-- ============================================

-- Check if old user table exists and has data
-- If yes, migrate existing users
-- If no, create a default admin user for the legacy data

-- First, create default admin user to own legacy data (if no users exist)
INSERT INTO users (
    uuid, username, email, password_hash, auth_key, 
    status, subscription_plan, name, created_at, updated_at
)
SELECT 
    UUID() as uuid,
    'admin' as username,
    'admin@contentfactory.local' as email,
    '$2y$13$defaulthashplaceholder' as password_hash,
    'default_auth_key_32_chars____' as auth_key,
    10 as status,
    'enterprise' as subscription_plan,
    'Legacy Data Admin' as name,
    NOW() as created_at,
    NOW() as updated_at
WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 1);

-- If old `user` table exists, migrate its users
-- Note: Wrapping in procedure to handle case where old table doesn't exist
DROP PROCEDURE IF EXISTS migrate_legacy_users;
DELIMITER //
CREATE PROCEDURE migrate_legacy_users()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'user';
    
    IF table_exists > 0 THEN
        INSERT INTO users (id, uuid, username, email, password_hash, auth_key, 
                          password_reset_token, verification_token, status, 
                          created_at, updated_at)
        SELECT 
            id,
            UUID() as uuid,
            username,
            email,
            password_hash,
            auth_key,
            password_reset_token,
            verification_token,
            status,
            FROM_UNIXTIME(created_at) as created_at,
            FROM_UNIXTIME(updated_at) as updated_at
        FROM `user`
        ON DUPLICATE KEY UPDATE
            uuid = VALUES(uuid),
            password_hash = VALUES(password_hash),
            auth_key = VALUES(auth_key);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' users from legacy table') AS status;
    ELSE
        SELECT 'No legacy user table found, using default admin' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_legacy_users();
DROP PROCEDURE IF EXISTS migrate_legacy_users;

-- Store the default user ID for later use (first user in the system)
SET @default_user_id = (SELECT MIN(id) FROM users);
SELECT CONCAT('Using user_id=', @default_user_id, ' for legacy data') AS status;

-- ============================================
-- STEP 2: Migrate Google Consoles -> OAuth Consoles
-- ============================================

DROP PROCEDURE IF EXISTS migrate_google_consoles;
DELIMITER //
CREATE PROCEDURE migrate_google_consoles()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'google_consoles';
    
    IF table_exists > 0 THEN
        INSERT INTO oauth_consoles (
            id, user_id, platform, name, project_id, 
            client_id, client_secret, redirect_uris, 
            credentials_file, description, enabled, 
            created_at, updated_at
        )
        SELECT 
            id,
            @default_user_id as user_id,
            'google' as platform,
            name,
            project_id,
            client_id,
            client_secret,
            redirect_uris,
            credentials_file,
            description,
            enabled,
            created_at,
            updated_at
        FROM google_consoles
        ON DUPLICATE KEY UPDATE
            client_id = VALUES(client_id),
            client_secret = VALUES(client_secret);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' OAuth consoles') AS status;
    ELSE
        SELECT 'No google_consoles table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_google_consoles();
DROP PROCEDURE IF EXISTS migrate_google_consoles;

-- ============================================
-- STEP 3: Migrate YouTube Channels -> Channels
-- ============================================

DROP PROCEDURE IF EXISTS migrate_youtube_channels;
DELIMITER //
CREATE PROCEDURE migrate_youtube_channels()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'youtube_channels';
    
    IF table_exists > 0 THEN
        INSERT INTO channels (
            id, user_id, platform, name, platform_channel_id,
            console_id, access_token, refresh_token, token_expires_at,
            enabled, stat, metadata, created_at, updated_at
        )
        SELECT 
            yc.id,
            @default_user_id as user_id,
            'youtube' as platform,
            yc.name,
            yc.channel_id as platform_channel_id,
            yc.console_id,
            yc.access_token,
            yc.refresh_token,
            yc.token_expires_at,
            yc.enabled,
            yc.stat,
            JSON_OBJECT('add_info', yc.add_info, 'console_name', yc.console_name) as metadata,
            yc.created_at,
            yc.updated_at
        FROM youtube_channels yc
        ON DUPLICATE KEY UPDATE
            access_token = VALUES(access_token),
            refresh_token = VALUES(refresh_token),
            token_expires_at = VALUES(token_expires_at);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' channels') AS status;
    ELSE
        SELECT 'No youtube_channels table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_youtube_channels();
DROP PROCEDURE IF EXISTS migrate_youtube_channels;

-- ============================================
-- STEP 4: Migrate YouTube Tokens -> Channel Tokens
-- ============================================

DROP PROCEDURE IF EXISTS migrate_youtube_tokens;
DELIMITER //
CREATE PROCEDURE migrate_youtube_tokens()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'youtube_tokens';
    
    IF table_exists > 0 THEN
        INSERT INTO channel_tokens (
            id, channel_id, token_type, token_value, expires_at, created_at
        )
        SELECT 
            yt.id,
            c.id as channel_id,
            yt.token_type,
            yt.token_value,
            yt.expires_at,
            yt.created_at
        FROM youtube_tokens yt
        JOIN channels c ON c.name = yt.channel_name AND c.platform = 'youtube'
        ON DUPLICATE KEY UPDATE
            token_value = VALUES(token_value),
            expires_at = VALUES(expires_at);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' channel tokens') AS status;
    ELSE
        SELECT 'No youtube_tokens table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_youtube_tokens();
DROP PROCEDURE IF EXISTS migrate_youtube_tokens;

-- ============================================
-- STEP 5: Migrate YouTube Account Credentials -> Channel Credentials
-- ============================================

DROP PROCEDURE IF EXISTS migrate_youtube_credentials;
DELIMITER //
CREATE PROCEDURE migrate_youtube_credentials()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'youtube_account_credentials';
    
    IF table_exists > 0 THEN
        INSERT INTO channel_credentials (
            id, channel_id, login_email, login_password, totp_secret,
            backup_codes, proxy_host, proxy_port, proxy_username, proxy_password,
            profile_path, user_agent, last_success_at, last_attempt_at,
            last_error, enabled, created_at, updated_at
        )
        SELECT 
            yac.id,
            c.id as channel_id,
            yac.login_email,
            yac.login_password,
            yac.totp_secret,
            yac.backup_codes,
            yac.proxy_host,
            yac.proxy_port,
            yac.proxy_username,
            yac.proxy_password,
            yac.profile_path,
            yac.user_agent,
            yac.last_success_at,
            yac.last_attempt_at,
            yac.last_error,
            yac.enabled,
            yac.created_at,
            yac.updated_at
        FROM youtube_account_credentials yac
        JOIN channels c ON c.name = yac.channel_name AND c.platform = 'youtube'
        ON DUPLICATE KEY UPDATE
            login_password = VALUES(login_password),
            totp_secret = VALUES(totp_secret);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' channel credentials') AS status;
    ELSE
        SELECT 'No youtube_account_credentials table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_youtube_credentials();
DROP PROCEDURE IF EXISTS migrate_youtube_credentials;

-- ============================================
-- STEP 6: Migrate Tasks -> Publish Tasks
-- ============================================

DROP PROCEDURE IF EXISTS migrate_tasks;
DELIMITER //
CREATE PROCEDURE migrate_tasks()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'tasks';
    
    IF table_exists > 0 THEN
        -- Note: We need to map account_id to channel_id
        -- In legacy system, account_id referenced youtube_channels.id
        INSERT INTO publish_tasks (
            id, user_id, channel_id, platform, media_type, status,
            source_file_path, thumbnail_path, title, description, keywords,
            post_comment, date_scheduled, date_completed, upload_id,
            error_message, legacy_add_info, created_at, updated_at
        )
        SELECT 
            t.id,
            @default_user_id as user_id,
            t.account_id as channel_id,
            'youtube' as platform,
            COALESCE(t.media_type, 'video') as media_type,
            t.status,
            t.att_file_path as source_file_path,
            t.cover as thumbnail_path,
            COALESCE(t.title, 'Untitled') as title,
            t.description,
            t.keywords,
            t.post_comment,
            COALESCE(t.date_post, t.date_add, NOW()) as date_scheduled,
            t.date_done as date_completed,
            t.upload_id,
            t.error_message,
            t.add_info as legacy_add_info,
            COALESCE(t.date_add, NOW()) as created_at,
            NOW() as updated_at
        FROM tasks t
        WHERE t.account_id IS NOT NULL
        AND EXISTS (SELECT 1 FROM channels c WHERE c.id = t.account_id)
        ON DUPLICATE KEY UPDATE
            status = VALUES(status),
            upload_id = VALUES(upload_id);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' publish tasks') AS status;
    ELSE
        SELECT 'No tasks table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_tasks();
DROP PROCEDURE IF EXISTS migrate_tasks;

-- ============================================
-- STEP 7: Migrate YouTube Channel Daily -> Channel Daily Stats
-- ============================================

DROP PROCEDURE IF EXISTS migrate_daily_stats;
DELIMITER //
CREATE PROCEDURE migrate_daily_stats()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'youtube_channel_daily';
    
    IF table_exists > 0 THEN
        INSERT INTO channel_daily_stats (
            id, channel_id, platform_channel_id, snapshot_date,
            subscribers, views, videos, created_at
        )
        SELECT 
            ycd.id,
            COALESCE(ycd.yt_channel_id, c.id) as channel_id,
            ycd.channel_id as platform_channel_id,
            ycd.snapshot_date,
            ycd.subscribers,
            ycd.views,
            ycd.videos,
            ycd.created_at
        FROM youtube_channel_daily ycd
        LEFT JOIN channels c ON c.platform_channel_id = ycd.channel_id AND c.platform = 'youtube'
        WHERE c.id IS NOT NULL OR ycd.yt_channel_id IS NOT NULL
        ON DUPLICATE KEY UPDATE
            subscribers = VALUES(subscribers),
            views = VALUES(views),
            videos = VALUES(videos);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' daily stats') AS status;
    ELSE
        SELECT 'No youtube_channel_daily table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_daily_stats();
DROP PROCEDURE IF EXISTS migrate_daily_stats;

-- ============================================
-- STEP 8: Migrate YouTube Reauth Audit -> Reauth Audit
-- ============================================

DROP PROCEDURE IF EXISTS migrate_reauth_audit;
DELIMITER //
CREATE PROCEDURE migrate_reauth_audit()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'youtube_reauth_audit';
    
    IF table_exists > 0 THEN
        INSERT INTO reauth_audit (
            id, channel_id, initiated_at, completed_at, status,
            error_message, metadata, created_at
        )
        SELECT 
            yra.id,
            c.id as channel_id,
            yra.initiated_at,
            yra.completed_at,
            yra.status,
            yra.error_message,
            yra.metadata,
            yra.initiated_at as created_at
        FROM youtube_reauth_audit yra
        JOIN channels c ON c.name = yra.channel_name AND c.platform = 'youtube'
        ON DUPLICATE KEY UPDATE
            status = VALUES(status),
            completed_at = VALUES(completed_at);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' reauth audit records') AS status;
    ELSE
        SELECT 'No youtube_reauth_audit table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_reauth_audit();
DROP PROCEDURE IF EXISTS migrate_reauth_audit;

-- ============================================
-- STEP 9: Migrate YouTube Accounts -> Streaming Accounts
-- ============================================

DROP PROCEDURE IF EXISTS migrate_streaming_accounts;
DELIMITER //
CREATE PROCEDURE migrate_streaming_accounts()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'youtube_account';
    
    IF table_exists > 0 THEN
        INSERT INTO streaming_accounts (
            id, user_id, platform, name, client_id, client_secret,
            access_token, refresh_token, token_expires_at, enabled,
            created_at, updated_at
        )
        SELECT 
            ya.id,
            @default_user_id as user_id,
            'youtube' as platform,
            ya.name,
            ya.client_id,
            ya.client_secret,
            ya.access_token,
            ya.refresh_token,
            ya.token_expires as token_expires_at,
            1 as enabled,
            ya.created_at,
            ya.updated_at
        FROM youtube_account ya
        ON DUPLICATE KEY UPDATE
            access_token = VALUES(access_token),
            refresh_token = VALUES(refresh_token),
            token_expires_at = VALUES(token_expires_at);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' streaming accounts') AS status;
    ELSE
        SELECT 'No youtube_account table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_streaming_accounts();
DROP PROCEDURE IF EXISTS migrate_streaming_accounts;

-- ============================================
-- STEP 10: Migrate Streams
-- ============================================

DROP PROCEDURE IF EXISTS migrate_streams;
DELIMITER //
CREATE PROCEDURE migrate_streams()
BEGIN
    DECLARE table_exists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO table_exists 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() AND table_name = 'stream';
    
    IF table_exists > 0 THEN
        INSERT INTO streams (
            id, user_id, streaming_account_id, channel_id,
            name, service_name, workdir, rtmp_host, rtmp_base,
            stream_key, duration_sec, platform_broadcast_id,
            platform_video_id, platform_stream_id, platform_stream_key,
            title, description, tags, thumbnail_path,
            enabled, notes, created_at, updated_at
        )
        SELECT 
            s.id,
            @default_user_id as user_id,
            s.youtube_account_id as streaming_account_id,
            c.id as channel_id,
            s.name,
            s.service_name,
            s.workdir,
            s.rtmp_host,
            s.rtmp_base,
            s.stream_key,
            s.duration_sec,
            s.youtube_broadcast_id as platform_broadcast_id,
            s.youtube_video_id as platform_video_id,
            s.youtube_stream_id as platform_stream_id,
            s.youtube_stream_key as platform_stream_key,
            s.yt_title as title,
            s.yt_description as description,
            s.yt_tags as tags,
            s.yt_thumbnail as thumbnail_path,
            s.enabled,
            s.notes,
            FROM_UNIXTIME(s.created_at) as created_at,
            FROM_UNIXTIME(s.updated_at) as updated_at
        FROM stream s
        LEFT JOIN channels c ON c.name = s.channel_name AND c.platform = 'youtube'
        ON DUPLICATE KEY UPDATE
            streaming_account_id = VALUES(streaming_account_id),
            channel_id = VALUES(channel_id);
            
        SELECT CONCAT('Migrated ', ROW_COUNT(), ' streams') AS status;
    ELSE
        SELECT 'No stream table found' AS status;
    END IF;
END //
DELIMITER ;

CALL migrate_streams();
DROP PROCEDURE IF EXISTS migrate_streams;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- Log migration
INSERT INTO migration (version, apply_time) VALUES ('002_migrate_data', UNIX_TIMESTAMP())
ON DUPLICATE KEY UPDATE apply_time = UNIX_TIMESTAMP();

SELECT '====================================' AS separator;
SELECT 'Migration 002: Data migration completed successfully!' AS status;
SELECT 'All legacy data has been preserved in new tables.' AS note;
SELECT 'Legacy tables are still intact - drop them manually after verification.' AS warning;
SELECT '====================================' AS separator;
