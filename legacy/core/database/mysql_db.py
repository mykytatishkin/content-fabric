#!/usr/bin/env python3
"""
MySQL Database module for managing channels, credentials, tasks and audit.

Refactored for new schema:
  platform_channels, platform_oauth_credentials,
  platform_channel_login_credentials, channel_reauth_audit_logs,
  content_upload_queue_tasks, platform_channel_tokens
"""

import mysql.connector
from mysql.connector import Error
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OAuthCredential:
    """OAuth console/app credentials (platform_oauth_credentials)."""
    id: int
    name: str
    client_id: str
    client_secret: str
    credentials_file: Optional[str] = None
    cloud_project_id: Optional[str] = None
    redirect_uris: Optional[List[str]] = None
    description: Optional[str] = None
    platform: str = 'google'
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Keep old name as alias for backward compatibility
GoogleConsole = OAuthCredential


@dataclass
class PlatformChannel:
    """Platform channel (platform_channels)."""
    id: int
    name: str
    platform_channel_id: str
    console_id: Optional[int] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    project_id: Optional[int] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Keep old name as alias for backward compatibility
YouTubeChannel = PlatformChannel


@dataclass
class ChannelLoginCredential:
    """RPA login credentials (platform_channel_login_credentials)."""
    id: int
    channel_id: int
    login_email: str
    login_password: str
    totp_secret: Optional[str] = None
    backup_codes: Optional[List[str]] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    profile_path: Optional[str] = None
    user_agent: Optional[str] = None
    last_success_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    last_error: Optional[str] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Keep old name as alias
YouTubeAccountCredential = ChannelLoginCredential


@dataclass
class ReauthAuditLog:
    """Reauth audit record (channel_reauth_audit_logs)."""
    id: int
    channel_id: int
    initiated_at: datetime
    completed_at: Optional[datetime]
    status: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# Keep old name as alias
YouTubeReauthAudit = ReauthAuditLog


@dataclass
class UploadTask:
    """Upload task (content_upload_queue_tasks).

    Status codes:
        0 -> pending
        1 -> completed
        2 -> failed
        3 -> processing
    """
    id: int
    channel_id: int
    media_type: str
    status: int
    source_file_path: str
    title: str
    scheduled_at: datetime
    created_at: Optional[datetime] = None
    thumbnail_path: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    post_comment: Optional[str] = None
    legacy_add_info: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None
    upload_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


# Keep old name as alias
Task = UploadTask


class YouTubeMySQLDatabase:
    """MySQL Database manager for channels, credentials and tasks."""

    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = self._get_default_config()
        self.config = config
        self.connection = None
        self._connect()

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', 3306)),
            'database': os.getenv('MYSQL_DATABASE', 'content_fabric'),
            'user': os.getenv('MYSQL_USER', 'content_fabric_user'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': True
        }

    def _connect(self):
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                print("Connected to MySQL database")
            else:
                raise Error("Failed to connect to MySQL")
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise

    def _ensure_connection(self):
        if not self.connection or not self.connection.is_connected():
            self._connect()

    def _execute_query(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[tuple]]:
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            else:
                self.connection.commit()
                return None
        except Error as e:
            print(f"Database error: {e}")
            self.connection.rollback()
            raise

    # ==================== Channel Methods ====================

    def add_channel(self, name: str, platform_channel_id: str, console_id: Optional[int] = None,
                   enabled: bool = True) -> bool:
        """Add a new channel to platform_channels."""
        try:
            project_id = self._get_default_project_id()
            query = """
                INSERT INTO platform_channels
                (project_id, name, platform_channel_id, console_id, enabled)
                VALUES (%s, %s, %s, %s, %s)
            """
            self._execute_query(query, (project_id, name, platform_channel_id, console_id, enabled))
            return True
        except Error as e:
            if e.errno == 1062:
                return False
            raise

    def get_channel(self, name: str) -> Optional[PlatformChannel]:
        """Get channel by name."""
        query = """
            SELECT id, name, platform_channel_id,
                   console_id, access_token, refresh_token, token_expires_at,
                   project_id, enabled, created_at, updated_at
            FROM platform_channels WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        if results:
            return self._row_to_channel(results[0])
        return None

    def get_channel_by_id(self, channel_id: int) -> Optional[PlatformChannel]:
        """Get channel by ID."""
        query = """
            SELECT id, name, platform_channel_id,
                   console_id, access_token, refresh_token, token_expires_at,
                   project_id, enabled, created_at, updated_at
            FROM platform_channels WHERE id = %s
        """
        results = self._execute_query(query, (channel_id,), fetch=True)
        if results:
            return self._row_to_channel(results[0])
        return None

    def get_channel_by_channel_id(self, platform_channel_id: str) -> Optional[PlatformChannel]:
        """Get channel by platform_channel_id."""
        query = """
            SELECT id, name, platform_channel_id,
                   console_id, access_token, refresh_token, token_expires_at,
                   project_id, enabled, created_at, updated_at
            FROM platform_channels WHERE platform_channel_id = %s
        """
        results = self._execute_query(query, (platform_channel_id,), fetch=True)
        if results:
            return self._row_to_channel(results[0])
        return None

    def get_all_channels(self, enabled_only: bool = False) -> List[PlatformChannel]:
        """Get all channels."""
        if enabled_only:
            query = """
                SELECT id, name, platform_channel_id,
                       console_id, access_token, refresh_token, token_expires_at,
                       project_id, enabled, created_at, updated_at
                FROM platform_channels WHERE enabled = 1
            """
        else:
            query = """
                SELECT id, name, platform_channel_id,
                       console_id, access_token, refresh_token, token_expires_at,
                       project_id, enabled, created_at, updated_at
                FROM platform_channels
            """
        results = self._execute_query(query, fetch=True)
        return [self._row_to_channel(row) for row in results]

    def _row_to_channel(self, row: tuple) -> PlatformChannel:
        """Convert DB row to PlatformChannel."""
        return PlatformChannel(
            id=row[0],
            name=row[1],
            platform_channel_id=row[2],
            console_id=row[3],
            access_token=row[4],
            refresh_token=row[5],
            token_expires_at=row[6],
            project_id=row[7],
            enabled=bool(row[8]),
            created_at=row[9],
            updated_at=row[10]
        )

    def update_channel_tokens(self, name: str, access_token: str,
                            refresh_token: Optional[str] = None,
                            expires_at: Optional[datetime] = None) -> bool:
        """Update channel tokens."""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            query = """
                UPDATE platform_channels
                SET access_token = %s, refresh_token = %s,
                    token_expires_at = %s, updated_at = NOW()
                WHERE name = %s
            """
            cursor.execute(query, (access_token, refresh_token, expires_at, name))
            self.connection.commit()
            rows_affected = cursor.rowcount
            cursor.close()
            if rows_affected == 0:
                print(f"Channel '{name}' not found")
                return False
            return True
        except Error as e:
            print(f"Error updating tokens for channel '{name}': {e}")
            return False

    def enable_channel(self, name: str) -> bool:
        return self._set_channel_enabled(name, True)

    def disable_channel(self, name: str) -> bool:
        return self._set_channel_enabled(name, False)

    def _set_channel_enabled(self, name: str, enabled: bool) -> bool:
        try:
            query = """
                UPDATE platform_channels
                SET enabled = %s, updated_at = NOW()
                WHERE name = %s
            """
            self._execute_query(query, (enabled, name))
            return True
        except Error:
            return False

    def delete_channel(self, name: str) -> bool:
        try:
            query = "DELETE FROM platform_channels WHERE name = %s"
            self._execute_query(query, (name,))
            return True
        except Error:
            return False

    def remove_channel(self, name: str) -> bool:
        return self.delete_channel(name)

    def is_token_expired(self, name: str) -> bool:
        channel = self.get_channel(name)
        if not channel or not channel.access_token:
            return True
        if not channel.token_expires_at:
            return False
        return datetime.now() >= channel.token_expires_at

    def get_expired_tokens(self) -> List[str]:
        expired_channels = []
        now = datetime.now()
        for channel in self.get_all_channels(enabled_only=True):
            if channel.token_expires_at and now >= channel.token_expires_at:
                expired_channels.append(channel.name)
        return expired_channels

    def get_expiring_tokens(self, days_ahead: int = 7) -> List[str]:
        expiring_channels = []
        now = datetime.now()
        threshold = now + timedelta(days=days_ahead)
        for channel in self.get_all_channels(enabled_only=True):
            if channel.token_expires_at and channel.token_expires_at <= threshold:
                expiring_channels.append(channel.name)
        return expiring_channels

    def get_channels_needing_reauth(self, expiry_threshold_hours: int = 24) -> tuple:
        no_token_channels: List[PlatformChannel] = []
        expiring_channels: List[PlatformChannel] = []
        now = datetime.now()
        threshold = now + timedelta(hours=expiry_threshold_hours)
        for channel in self.get_all_channels(enabled_only=True):
            if not channel.access_token or not channel.refresh_token:
                no_token_channels.append(channel)
                continue
            if channel.token_expires_at and channel.token_expires_at <= threshold:
                expiring_channels.append(channel)
        return no_token_channels, expiring_channels

    def export_config(self) -> Dict[str, Any]:
        config = {'accounts': {'youtube': []}}
        for channel in self.get_all_channels():
            credentials = self.get_console_credentials_for_channel(channel.name)
            if credentials:
                client_id = credentials['client_id']
                client_secret = credentials['client_secret']
                credentials_file = credentials.get('credentials_file', 'credentials.json')
            else:
                client_id = ''
                client_secret = ''
                credentials_file = 'credentials.json'
            config['accounts']['youtube'].append({
                'name': channel.name,
                'platform_channel_id': channel.platform_channel_id,
                'console_id': channel.console_id,
                'client_id': client_id,
                'client_secret': client_secret,
                'credentials_file': credentials_file,
                'enabled': channel.enabled
            })
        return config

    def import_from_config(self, config: Dict[str, Any]) -> int:
        imported_count = 0
        youtube_accounts = config.get('accounts', {}).get('youtube', [])
        for account in youtube_accounts:
            if self.add_channel(
                name=account.get('name'),
                platform_channel_id=account.get('platform_channel_id', account.get('channel_id', '')),
                console_id=account.get('console_id'),
                enabled=account.get('enabled', True)
            ):
                imported_count += 1
        return imported_count

    # ==================== OAuth Credential Methods ====================

    def add_google_console(self, name: str, client_id: str, client_secret: str,
                          credentials_file: Optional[str] = None,
                          description: Optional[str] = None,
                          enabled: bool = True) -> bool:
        """Add a new OAuth credential to platform_oauth_credentials."""
        try:
            project_id = self._get_default_project_id()
            query = """
                INSERT INTO platform_oauth_credentials
                (project_id, name, client_id, client_secret, credentials_file, description, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (project_id, name, client_id, client_secret, credentials_file, description, enabled))
            return True
        except Error as e:
            if e.errno == 1062:
                return False
            raise

    def get_google_console(self, name: str) -> Optional[OAuthCredential]:
        """Get OAuth credential by name."""
        query = """
            SELECT id, name, cloud_project_id, client_id, client_secret, credentials_file,
                   redirect_uris, description, enabled, created_at, updated_at
            FROM platform_oauth_credentials WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        if results:
            return self._row_to_oauth_credential(results[0])
        return None

    def get_all_google_consoles(self, enabled_only: bool = False) -> List[OAuthCredential]:
        """Get all OAuth credentials."""
        if enabled_only:
            query = """
                SELECT id, name, cloud_project_id, client_id, client_secret, credentials_file,
                       redirect_uris, description, enabled, created_at, updated_at
                FROM platform_oauth_credentials WHERE enabled = 1
            """
        else:
            query = """
                SELECT id, name, cloud_project_id, client_id, client_secret, credentials_file,
                       redirect_uris, description, enabled, created_at, updated_at
                FROM platform_oauth_credentials
            """
        results = self._execute_query(query, fetch=True)
        return [self._row_to_oauth_credential(row) for row in results]

    def _row_to_oauth_credential(self, row: tuple) -> OAuthCredential:
        """Convert DB row to OAuthCredential."""
        redirect_uris = None
        if row[6]:
            try:
                redirect_uris = json.loads(row[6]) if isinstance(row[6], str) else row[6]
            except (json.JSONDecodeError, TypeError):
                redirect_uris = None
        return OAuthCredential(
            id=row[0],
            name=row[1],
            cloud_project_id=row[2],
            client_id=row[3],
            client_secret=row[4],
            credentials_file=row[5],
            redirect_uris=redirect_uris,
            description=row[7],
            enabled=bool(row[8]),
            created_at=row[9],
            updated_at=row[10]
        )

    def update_google_console(self, name: str, client_id: Optional[str] = None,
                              client_secret: Optional[str] = None,
                              credentials_file: Optional[str] = None,
                              description: Optional[str] = None,
                              enabled: Optional[bool] = None) -> bool:
        try:
            updates = []
            params = []
            if client_id is not None:
                updates.append("client_id = %s")
                params.append(client_id)
            if client_secret is not None:
                updates.append("client_secret = %s")
                params.append(client_secret)
            if credentials_file is not None:
                updates.append("credentials_file = %s")
                params.append(credentials_file)
            if description is not None:
                updates.append("description = %s")
                params.append(description)
            if enabled is not None:
                updates.append("enabled = %s")
                params.append(enabled)
            if not updates:
                return False
            updates.append("updated_at = NOW()")
            params.append(name)
            query = f"UPDATE platform_oauth_credentials SET {', '.join(updates)} WHERE name = %s"
            self._execute_query(query, tuple(params))
            return True
        except Error:
            return False

    def delete_google_console(self, name: str) -> bool:
        try:
            query = "DELETE FROM platform_oauth_credentials WHERE name = %s"
            self._execute_query(query, (name,))
            return True
        except Error:
            return False

    def get_console_credentials_for_channel(self, channel_name: str) -> Optional[Dict[str, str]]:
        """Get OAuth credentials for a channel from its associated console."""
        channel = self.get_channel(channel_name)
        if not channel:
            return None
        if channel.console_id:
            console = self.get_console(channel.console_id)
            if console and console.enabled:
                return {
                    'client_id': console.client_id,
                    'client_secret': console.client_secret,
                    'credentials_file': console.credentials_file or 'credentials.json'
                }
        return None

    def get_database_stats(self) -> Dict[str, Any]:
        try:
            channel_count = self._execute_query("SELECT COUNT(*) FROM platform_channels", fetch=True)[0][0]
            enabled_count = self._execute_query("SELECT COUNT(*) FROM platform_channels WHERE enabled = 1", fetch=True)[0][0]
            token_count = self._execute_query("SELECT COUNT(*) FROM platform_channel_tokens", fetch=True)[0][0]
            expired_count = len(self.get_expired_tokens())
            try:
                console_count = self._execute_query("SELECT COUNT(*) FROM platform_oauth_credentials", fetch=True)[0][0]
            except (Error, IndexError, TypeError):
                console_count = 0
            try:
                task_count = self._execute_query("SELECT COUNT(*) FROM content_upload_queue_tasks", fetch=True)[0][0]
                pending_count = self._execute_query("SELECT COUNT(*) FROM content_upload_queue_tasks WHERE status = 0", fetch=True)[0][0]
                completed_count = self._execute_query("SELECT COUNT(*) FROM content_upload_queue_tasks WHERE status = 1", fetch=True)[0][0]
                failed_count = self._execute_query("SELECT COUNT(*) FROM content_upload_queue_tasks WHERE status = 2", fetch=True)[0][0]
            except (Error, IndexError, TypeError):
                task_count = pending_count = completed_count = failed_count = 0
            return {
                'total_channels': channel_count,
                'enabled_channels': enabled_count,
                'disabled_channels': channel_count - enabled_count,
                'total_tokens': token_count,
                'expired_tokens': expired_count,
                'total_consoles': console_count,
                'total_tasks': task_count,
                'pending_tasks': pending_count,
                'completed_tasks': completed_count,
                'failed_tasks': failed_count
            }
        except Error as e:
            print(f"Error getting database stats: {e}")
            return {}

    # ==================== Login Credential Management ====================

    def upsert_account_credentials(
        self,
        channel_id: int,
        login_email: str,
        login_password: str,
        totp_secret: Optional[str] = None,
        backup_codes: Optional[List[str]] = None,
        proxy_host: Optional[str] = None,
        proxy_port: Optional[int] = None,
        proxy_username: Optional[str] = None,
        proxy_password: Optional[str] = None,
        profile_path: Optional[str] = None,
        user_agent: Optional[str] = None,
        enabled: bool = True
    ) -> bool:
        """Create or update login credentials for a channel."""
        try:
            backup_codes_json = json.dumps(backup_codes) if backup_codes else None
            query = """
                INSERT INTO platform_channel_login_credentials (
                    channel_id,
                    login_email, login_password,
                    totp_secret, backup_codes,
                    proxy_host, proxy_port, proxy_username, proxy_password,
                    profile_path, user_agent, enabled
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    login_email = VALUES(login_email),
                    login_password = VALUES(login_password),
                    totp_secret = VALUES(totp_secret),
                    backup_codes = VALUES(backup_codes),
                    proxy_host = VALUES(proxy_host),
                    proxy_port = VALUES(proxy_port),
                    proxy_username = VALUES(proxy_username),
                    proxy_password = VALUES(proxy_password),
                    profile_path = VALUES(profile_path),
                    user_agent = VALUES(user_agent),
                    enabled = VALUES(enabled),
                    updated_at = CURRENT_TIMESTAMP
            """
            params = (
                channel_id,
                login_email, login_password,
                totp_secret, backup_codes_json,
                proxy_host, proxy_port, proxy_username, proxy_password,
                profile_path, user_agent, enabled
            )
            self._execute_query(query, params)
            return True
        except Error as e:
            print(f"Error upserting credentials for channel_id={channel_id}: {e}")
            return False

    def disable_account_credentials(self, channel_id: int) -> bool:
        """Disable credentials for a channel."""
        try:
            query = """
                UPDATE platform_channel_login_credentials
                SET enabled = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = %s
            """
            self._execute_query(query, (channel_id,))
            return True
        except Error as e:
            print(f"Error disabling credentials for channel_id={channel_id}: {e}")
            return False

    def get_account_credentials(
        self,
        channel_id: int,
        include_disabled: bool = False
    ) -> Optional[ChannelLoginCredential]:
        """Fetch login credentials for a channel."""
        try:
            query = """
                SELECT
                    id, channel_id,
                    login_email, login_password,
                    totp_secret, backup_codes,
                    proxy_host, proxy_port, proxy_username, proxy_password,
                    profile_path, user_agent,
                    last_success_at, last_attempt_at, last_error,
                    enabled, created_at, updated_at
                FROM platform_channel_login_credentials
                WHERE channel_id = %s
            """
            if not include_disabled:
                query += " AND enabled = TRUE"
            results = self._execute_query(query, (channel_id,), fetch=True)
            if not results:
                return None
            return self._row_to_credentials(results[0])
        except Error as e:
            print(f"Error fetching credentials for channel_id={channel_id}: {e}")
            return None

    def get_account_credentials_by_name(
        self,
        channel_name: str,
        include_disabled: bool = False
    ) -> Optional[ChannelLoginCredential]:
        """Fetch login credentials by channel name (convenience wrapper)."""
        channel = self.get_channel(channel_name)
        if not channel:
            return None
        return self.get_account_credentials(channel.id, include_disabled)

    def list_account_credentials(self, limit: Optional[int] = None) -> List[ChannelLoginCredential]:
        """List all login credentials."""
        try:
            query = """
                SELECT
                    id, channel_id,
                    login_email, login_password,
                    totp_secret, backup_codes,
                    proxy_host, proxy_port, proxy_username, proxy_password,
                    profile_path, user_agent,
                    last_success_at, last_attempt_at, last_error,
                    enabled, created_at, updated_at
                FROM platform_channel_login_credentials
                ORDER BY channel_id ASC
            """
            if limit:
                results = self._execute_query(query + " LIMIT %s", (limit,), fetch=True)
            else:
                results = self._execute_query(query, fetch=True)
            return [self._row_to_credentials(row) for row in results]
        except Error as e:
            print(f"Error listing credentials: {e}")
            return []

    def mark_credentials_attempt(
        self,
        channel_id: int,
        success: bool,
        error_message: Optional[str] = None,
        attempt_time: Optional[datetime] = None
    ) -> bool:
        """Update credential metadata after an automation attempt."""
        try:
            attempt_time = attempt_time or datetime.now()
            query = """
                UPDATE platform_channel_login_credentials
                SET
                    last_attempt_at = %s,
                    last_success_at = CASE WHEN %s THEN %s ELSE last_success_at END,
                    last_error = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = %s
            """
            params = (
                attempt_time,
                success,
                attempt_time if success else None,
                None if success else error_message,
                channel_id
            )
            self._execute_query(query, params)
            return True
        except Error as e:
            print(f"Error updating credentials attempt for channel_id={channel_id}: {e}")
            return False

    def update_profile_path(self, channel_id: int, profile_path: str) -> bool:
        """Update profile_path for a channel's credentials."""
        try:
            query = """
                UPDATE platform_channel_login_credentials
                SET profile_path = %s, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = %s
            """
            self._execute_query(query, (profile_path, channel_id))
            return True
        except Error as e:
            print(f"Error updating profile_path for channel_id={channel_id}: {e}")
            return False

    # ==================== Re-auth Audit ====================

    def create_reauth_audit(
        self,
        channel_id: int,
        status: str,
        initiated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """Create an audit record in channel_reauth_audit_logs."""
        try:
            initiated_at = initiated_at or datetime.now()
            metadata_json = json.dumps(metadata) if metadata else None
            query = """
                INSERT INTO channel_reauth_audit_logs (
                    channel_id, initiated_at, status, metadata
                )
                VALUES (%s, %s, %s, %s)
            """
            self._execute_query(query, (channel_id, initiated_at, status, metadata_json))
            result = self._execute_query("SELECT LAST_INSERT_ID()", fetch=True)
            return result[0][0] if result else None
        except Error as e:
            print(f"Error creating reauth audit for channel_id={channel_id}: {e}")
            return None

    def complete_reauth_audit(
        self,
        audit_id: int,
        status: str,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update an audit record with completion status."""
        try:
            completed_at = completed_at or datetime.now()
            metadata_json = json.dumps(metadata) if metadata else None
            query = """
                UPDATE channel_reauth_audit_logs
                SET
                    completed_at = %s,
                    status = %s,
                    error_message = %s,
                    metadata = COALESCE(%s, metadata)
                WHERE id = %s
            """
            self._execute_query(query, (completed_at, status, error_message, metadata_json, audit_id))
            return True
        except Error as e:
            print(f"Error completing reauth audit #{audit_id}: {e}")
            return False

    def get_recent_reauth_audit(
        self,
        channel_id: int,
        limit: int = 10
    ) -> List[ReauthAuditLog]:
        """Retrieve recent audit entries for a channel."""
        try:
            query = """
                SELECT
                    id, channel_id,
                    initiated_at, completed_at,
                    status, error_message, metadata
                FROM channel_reauth_audit_logs
                WHERE channel_id = %s
                ORDER BY initiated_at DESC
                LIMIT %s
            """
            results = self._execute_query(query, (channel_id, limit), fetch=True)
            return [self._row_to_audit(row) for row in results]
        except Error as e:
            print(f"Error fetching reauth audit for channel_id={channel_id}: {e}")
            return []

    # ==================== Task Management ====================

    def create_task(self, channel_id: int, source_file_path: str, title: str,
                   scheduled_at: datetime, media_type: str = 'youtube',
                   thumbnail_path: Optional[str] = None, description: Optional[str] = None,
                   keywords: Optional[str] = None, post_comment: Optional[str] = None,
                   legacy_add_info: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Create a new task in content_upload_queue_tasks."""
        try:
            project_id = self._get_default_project_id()
            add_info_json = json.dumps(legacy_add_info) if legacy_add_info else None
            query = """
                INSERT INTO content_upload_queue_tasks
                (project_id, channel_id, media_type, source_file_path, thumbnail_path,
                 title, description, keywords, post_comment, legacy_add_info, scheduled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (
                project_id, channel_id, media_type, source_file_path, thumbnail_path,
                title, description, keywords, post_comment, add_info_json, scheduled_at
            ))
            result = self._execute_query("SELECT LAST_INSERT_ID()", fetch=True)
            return result[0][0] if result else None
        except Error as e:
            print(f"Error creating task: {e}")
            return None

    def get_task(self, task_id: int) -> Optional[UploadTask]:
        """Get task by ID."""
        query = """
            SELECT id, channel_id, media_type, status, created_at, source_file_path,
                   thumbnail_path, title, description, keywords, post_comment, legacy_add_info,
                   scheduled_at, completed_at, upload_id
            FROM content_upload_queue_tasks WHERE id = %s
        """
        results = self._execute_query(query, (task_id,), fetch=True)
        if results:
            return self._row_to_task(results[0])
        return None

    def get_pending_tasks(self, limit: Optional[int] = None) -> List[UploadTask]:
        """Get all pending tasks ready to execute."""
        query = """
            SELECT id, channel_id, media_type, status, created_at, source_file_path,
                   thumbnail_path, title, description, keywords, post_comment, legacy_add_info,
                   scheduled_at, completed_at, upload_id
            FROM content_upload_queue_tasks
            WHERE status = 0 AND scheduled_at <= NOW()
            ORDER BY scheduled_at ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        results = self._execute_query(query, fetch=True)
        return [self._row_to_task(row) for row in results]

    def get_all_tasks(self, status: Optional[int] = None,
                     channel_id: Optional[int] = None,
                     limit: Optional[int] = None) -> List[UploadTask]:
        """Get all tasks with optional filtering."""
        query = """
            SELECT id, channel_id, media_type, status, created_at, source_file_path,
                   thumbnail_path, title, description, keywords, post_comment, legacy_add_info,
                   scheduled_at, completed_at, upload_id
            FROM content_upload_queue_tasks WHERE 1=1
        """
        params = []
        if status is not None:
            query += " AND status = %s"
            params.append(status)
        if channel_id is not None:
            query += " AND channel_id = %s"
            params.append(channel_id)
        query += " ORDER BY scheduled_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        results = self._execute_query(query, tuple(params) if params else None, fetch=True)
        return [self._row_to_task(row) for row in results]

    def get_token_related_failed_tasks(self, channel_id: int) -> List[UploadTask]:
        """Get failed tasks with token-related errors for a channel."""
        query = """
            SELECT id, channel_id, media_type, status, created_at, source_file_path,
                   thumbnail_path, title, description, keywords, post_comment, legacy_add_info,
                   scheduled_at, completed_at, upload_id, error_message
            FROM content_upload_queue_tasks
            WHERE status = 2
            AND channel_id = %s
            AND error_message IS NOT NULL
            AND (
                error_message LIKE %s OR
                error_message LIKE %s OR
                error_message LIKE %s OR
                error_message LIKE %s OR
                error_message LIKE %s
            )
            ORDER BY scheduled_at ASC
        """
        params = (
            channel_id,
            '%invalid_grant%',
            '%Token has been expired or revoked%',
            '%refresh token%invalid%',
            '%refresh token%revoked%',
            '%token expired%'
        )
        results = self._execute_query(query, params, fetch=True)
        return [self._row_to_task(row) for row in results]

    def update_task_status(self, task_id: int, status: int,
                          error_message: Optional[str] = None,
                          completed_at: Optional[datetime] = None) -> bool:
        """Update task status."""
        try:
            if completed_at is None and status == 1:
                completed_at = datetime.now()
            query = """
                UPDATE content_upload_queue_tasks
                SET status = %s, completed_at = %s, error_message = %s
                WHERE id = %s
            """
            self._execute_query(query, (status, completed_at, error_message, task_id))
            return True
        except Error as e:
            print(f"Error updating task status: {e}")
            return False

    def mark_task_processing(self, task_id: int) -> bool:
        return self.update_task_status(task_id, 3)

    def mark_task_completed(self, task_id: int, upload_id: Optional[str] = None) -> bool:
        try:
            completed_at = datetime.now()
            query = """
                UPDATE content_upload_queue_tasks
                SET status = %s, completed_at = %s, upload_id = %s
                WHERE id = %s
            """
            self._execute_query(query, (1, completed_at, upload_id, task_id))
            return True
        except Error as e:
            print(f"Error marking task completed: {e}")
            return False

    def mark_task_failed(self, task_id: int, error_message: str = None) -> bool:
        return self.update_task_status(task_id, 2, error_message=error_message)

    def update_task_upload_id(self, task_id: int, upload_id: str) -> bool:
        try:
            query = """
                UPDATE content_upload_queue_tasks
                SET upload_id = %s
                WHERE id = %s
            """
            self._execute_query(query, (upload_id, task_id))
            return True
        except Error as e:
            print(f"Error updating task upload_id: {e}")
            return False

    def increment_task_retry(self, _task_id: int) -> bool:
        return True

    def delete_task(self, task_id: int) -> bool:
        try:
            query = "DELETE FROM content_upload_queue_tasks WHERE id = %s"
            self._execute_query(query, (task_id,))
            return True
        except Error:
            return False

    # ==================== Row Converters ====================

    def _row_to_credentials(self, row: tuple) -> ChannelLoginCredential:
        backup_codes = None
        if row[5]:
            try:
                backup_codes = json.loads(row[5])
            except (json.JSONDecodeError, TypeError):
                backup_codes = None
        return ChannelLoginCredential(
            id=row[0],
            channel_id=row[1],
            login_email=row[2],
            login_password=row[3],
            totp_secret=row[4],
            backup_codes=backup_codes,
            proxy_host=row[6],
            proxy_port=row[7],
            proxy_username=row[8],
            proxy_password=row[9],
            profile_path=row[10],
            user_agent=row[11],
            last_success_at=row[12],
            last_attempt_at=row[13],
            last_error=row[14],
            enabled=bool(row[15]),
            created_at=row[16],
            updated_at=row[17]
        )

    def _row_to_audit(self, row: tuple) -> ReauthAuditLog:
        metadata = None
        if row[6]:
            try:
                metadata = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                metadata = None
        return ReauthAuditLog(
            id=row[0],
            channel_id=row[1],
            initiated_at=row[2],
            completed_at=row[3],
            status=row[4],
            error_message=row[5],
            metadata=metadata
        )

    def _row_to_task(self, row: tuple) -> UploadTask:
        legacy_add_info = None
        if row[11]:
            try:
                legacy_add_info = json.loads(row[11])
            except (json.JSONDecodeError, TypeError):
                pass
        error_message = None
        if len(row) > 15:
            error_message = row[15]
        return UploadTask(
            id=row[0],
            channel_id=row[1],
            media_type=row[2],
            status=row[3],
            created_at=row[4],
            source_file_path=row[5],
            thumbnail_path=row[6],
            title=row[7],
            description=row[8],
            keywords=row[9],
            post_comment=row[10],
            legacy_add_info=legacy_add_info,
            scheduled_at=row[12],
            completed_at=row[13],
            upload_id=row[14] if len(row) > 14 else None,
            error_message=error_message,
            retry_count=0
        )

    # ==================== Console Management ====================

    def add_console(self, name: str, client_id: str, client_secret: str,
                   cloud_project_id: Optional[str] = None,
                   credentials_file: Optional[str] = None,
                   redirect_uris: Optional[List[str]] = None,
                   description: Optional[str] = None,
                   enabled: bool = True) -> bool:
        """Add a new OAuth credential."""
        try:
            project_id = self._get_default_project_id()
            redirect_uris_json = json.dumps(redirect_uris) if redirect_uris else None
            query = """
                INSERT INTO platform_oauth_credentials
                (project_id, name, cloud_project_id, client_id, client_secret,
                 credentials_file, redirect_uris, description, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (project_id, name, cloud_project_id, client_id, client_secret,
                                       credentials_file, redirect_uris_json, description, enabled))
            return True
        except Error as e:
            if e.errno == 1062:
                return False
            raise

    def get_console(self, console_id: int) -> Optional[OAuthCredential]:
        """Get OAuth credential by ID."""
        query = """
            SELECT id, name, cloud_project_id, client_id, client_secret, credentials_file,
                   redirect_uris, description, enabled, created_at, updated_at
            FROM platform_oauth_credentials WHERE id = %s
        """
        results = self._execute_query(query, (console_id,), fetch=True)
        if results:
            return self._row_to_oauth_credential(results[0])
        return None

    def get_console_by_name(self, name: str) -> Optional[OAuthCredential]:
        """Get OAuth credential by name."""
        query = """
            SELECT id, name, cloud_project_id, client_id, client_secret, credentials_file,
                   redirect_uris, description, enabled, created_at, updated_at
            FROM platform_oauth_credentials WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        if results:
            return self._row_to_oauth_credential(results[0])
        return None

    def get_all_consoles(self, enabled_only: bool = False) -> List[OAuthCredential]:
        """Get all OAuth credentials."""
        return self.get_all_google_consoles(enabled_only)

    def update_channel_console(self, channel_name: str, console_id: Optional[int]) -> bool:
        """Update console_id for a channel."""
        try:
            query = """
                UPDATE platform_channels
                SET console_id = %s, updated_at = NOW()
                WHERE name = %s
            """
            self._execute_query(query, (console_id, channel_name))
            return True
        except Error:
            return False

    def get_console_for_channel(self, channel_name: str) -> Optional[OAuthCredential]:
        """Get the OAuth credential associated with a channel."""
        channel = self.get_channel(channel_name)
        if not channel or not channel.console_id:
            return None
        return self.get_console(channel.console_id)

    # ==================== Helpers ====================

    def _get_default_project_id(self) -> int:
        """Get default project ID."""
        result = self._execute_query(
            "SELECT id FROM platform_projects WHERE slug = 'default' LIMIT 1",
            fetch=True
        )
        if result:
            return result[0][0]
        raise Error("No default project found. Run migration 002 first.")

    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("MySQL connection closed")


# Global database instance
_mysql_db_instance = None

def get_mysql_database(config: Dict[str, Any] = None) -> YouTubeMySQLDatabase:
    """Get global MySQL database instance."""
    global _mysql_db_instance
    if _mysql_db_instance is None:
        _mysql_db_instance = YouTubeMySQLDatabase(config)
    return _mysql_db_instance
