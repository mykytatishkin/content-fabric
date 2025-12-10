#!/usr/bin/env python3
"""
MySQL Database module for managing YouTube channels and tokens.
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
class GoogleConsole:
    """Google Cloud Console credentials data structure."""
    id: int
    name: str  # Unique identifier for the console
    client_id: str
    client_secret: str
    credentials_file: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class YouTubeChannel:
    """YouTube channel data structure."""
    id: int
    name: str
    channel_id: str
    console_name: Optional[str] = None  # Reference to google_consoles.name
    client_id: Optional[str] = None  # Deprecated: kept for backward compatibility
    client_secret: Optional[str] = None  # Deprecated: kept for backward compatibility
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    console_id: Optional[int] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class YouTubeAccountCredential:
    """Credentials required for automated OAuth re-authentication."""
    id: int
    channel_name: str
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


@dataclass
class YouTubeReauthAudit:
    """Audit record for OAuth re-authentication attempts."""
    id: int
    channel_name: str
    initiated_at: datetime
    completed_at: Optional[datetime]
    status: str
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Task:
    """Task data structure for scheduled posting.

    Status codes:
        0 -> pending
        1 -> completed
        2 -> failed
        3 -> processing
    """
    id: int
    account_id: int
    media_type: str
    status: int
    att_file_path: str
    title: str
    date_post: datetime
    date_add: Optional[datetime] = None
    cover: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    post_comment: Optional[str] = None
    add_info: Optional[Dict[str, Any]] = None
    date_done: Optional[datetime] = None
    upload_id: Optional[str] = None  # Video ID from platform after upload
    error_message: Optional[str] = None
    retry_count: int = 0


class YouTubeMySQLDatabase:
    """MySQL Database manager for YouTube channels and tokens."""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize MySQL database connection.
        
        Args:
            config: MySQL connection configuration dict with keys:
                   host, port, database, user, password, charset, collation
        """
        if config is None:
            config = self._get_default_config()
        
        self.config = config
        self.connection = None
        self._connect()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default MySQL configuration from environment variables."""
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
        """Connect to MySQL database."""
        try:
            self.connection = mysql.connector.connect(**self.config)
            if self.connection.is_connected():
                print("✅ Connected to MySQL database")
            else:
                raise Error("Failed to connect to MySQL")
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            raise
    
    def _ensure_connection(self):
        """Ensure database connection is active."""
        if not self.connection or not self.connection.is_connected():
            self._connect()
    
    def _execute_query(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[List[tuple]]:
        """Execute a SQL query and return results if fetch=True."""
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
            print(f"❌ Database error: {e}")
            self.connection.rollback()
            raise
    
    def add_channel(self, name: str, channel_id: str, console_name: Optional[str] = None,
                   client_id: Optional[str] = None, client_secret: Optional[str] = None,
                   enabled: bool = True) -> bool:
        """Add a new YouTube channel.
        
        Args:
            name: Channel name
            channel_id: YouTube channel ID
            console_name: Reference to google_consoles.name (preferred)
            client_id: OAuth client ID (deprecated, use console_name instead)
            client_secret: OAuth client secret (deprecated, use console_name instead)
            enabled: Whether channel is enabled
        """
        try:
            query = """
                INSERT INTO youtube_channels 
                (name, channel_id, console_name, client_id, client_secret, enabled)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (name, channel_id, console_name, client_id, client_secret, enabled))
            return True
        except Error as e:
            if e.errno == 1062:  # Duplicate entry
                return False
            raise
    
    def get_channel(self, name: str) -> Optional[YouTubeChannel]:
        """Get channel by name."""
        query = """
            SELECT id, name, channel_id, console_name, client_id, client_secret,
                   access_token, refresh_token, token_expires_at,
                   console_id, enabled, created_at, updated_at
            FROM youtube_channels WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        
        if results:
            row = results[0]
            return YouTubeChannel(
                id=row[0],
                name=row[1],
                channel_id=row[2],
                console_name=row[3],
                client_id=row[4],
                client_secret=row[5],
                access_token=row[6],
                refresh_token=row[7],
                token_expires_at=row[8],
                console_id=row[9],
                enabled=bool(row[10]),
                created_at=row[11],
                updated_at=row[12]
            )
        return None
    
    def get_all_channels(self, enabled_only: bool = False) -> List[YouTubeChannel]:
        """Get all channels."""
        if enabled_only:
            query = """
                SELECT id, name, channel_id, console_name, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       console_id, enabled, created_at, updated_at
                FROM youtube_channels WHERE enabled = 1
            """
        else:
            query = """
                SELECT id, name, channel_id, console_name, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       console_id, enabled, created_at, updated_at
                FROM youtube_channels
            """
        
        results = self._execute_query(query, fetch=True)
        channels = []
        
        for row in results:
            channels.append(YouTubeChannel(
                id=row[0],
                name=row[1],
                channel_id=row[2],
                console_name=row[3],
                client_id=row[4],
                client_secret=row[5],
                access_token=row[6],
                refresh_token=row[7],
                token_expires_at=row[8],
                console_id=row[9],
                enabled=bool(row[10]),
                created_at=row[11],
                updated_at=row[12]
            ))
        
        return channels
    
    def update_channel_tokens(self, name: str, access_token: str, 
                            refresh_token: Optional[str] = None,
                            expires_at: Optional[datetime] = None) -> bool:
        """Update channel tokens."""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            query = """
                UPDATE youtube_channels 
                SET access_token = %s, refresh_token = %s, 
                    token_expires_at = %s, updated_at = NOW()
                WHERE name = %s
            """
            cursor.execute(query, (access_token, refresh_token, expires_at, name))
            self.connection.commit()
            
            # Проверить, была ли обновлена хотя бы одна запись
            rows_affected = cursor.rowcount
            cursor.close()
            
            if rows_affected == 0:
                print(f"⚠️ Канал '{name}' не найден в базе данных")
                return False
            
            print(f"✅ Токены обновлены для канала '{name}'")
            return True
        except Error as e:
            print(f"❌ Ошибка обновления токенов для канала '{name}': {e}")
            return False
    
    def enable_channel(self, name: str) -> bool:
        """Enable a channel."""
        return self._set_channel_enabled(name, True)
    
    def disable_channel(self, name: str) -> bool:
        """Disable a channel."""
        return self._set_channel_enabled(name, False)
    
    def _set_channel_enabled(self, name: str, enabled: bool) -> bool:
        """Set channel enabled status."""
        try:
            query = """
                UPDATE youtube_channels 
                SET enabled = %s, updated_at = NOW()
                WHERE name = %s
            """
            self._execute_query(query, (enabled, name))
            return True
        except Error:
            return False
    
    def delete_channel(self, name: str) -> bool:
        """Delete a channel."""
        try:
            query = "DELETE FROM youtube_channels WHERE name = %s"
            self._execute_query(query, (name,))
            return True
        except Error:
            return False
    
    def remove_channel(self, name: str) -> bool:
        """Remove a channel from database."""
        return self.delete_channel(name)
    
    def is_token_expired(self, name: str) -> bool:
        """Check if channel token is expired.
        
        A token is considered expired if:
        1. Channel doesn't exist
        2. No access_token is present
        3. token_expires_at is set AND current time >= expiration time
        
        Note: If token_expires_at is None but access_token exists, 
        the token is NOT considered expired (it may be refreshable).
        """
        channel = self.get_channel(name)
        if not channel or not channel.access_token:
            return True
        
        # If no expiry date is set, but we have an access token,
        # don't consider it expired (it can be refreshed)
        if not channel.token_expires_at:
            return False
        
        return datetime.now() >= channel.token_expires_at
    
    def get_expired_tokens(self) -> List[str]:
        """Get list of channels with expired tokens.
        
        Only returns channels that have token_expires_at set and are actually expired.
        Channels without expiration dates are not included.
        """
        expired_channels = []
        now = datetime.now()
        for channel in self.get_all_channels(enabled_only=True):
            # Only consider channels with a valid expiration date
            if channel.token_expires_at:
                # Check if token is expired (current time >= expiration time)
                if now >= channel.token_expires_at:
                    expired_channels.append(channel.name)
        return expired_channels
    
    def get_expiring_tokens(self, days_ahead: int = 7) -> List[str]:
        """Get list of channels with tokens expiring soon or already expired.
        
        Args:
            days_ahead: Number of days to look ahead for expiring tokens (default: 7)
        
        Returns:
            List of channel names with tokens expiring within the specified days or already expired.
            Only includes channels that have token_expires_at set.
        """
        expiring_channels = []
        now = datetime.now()
        threshold = now + timedelta(days=days_ahead)
        
        for channel in self.get_all_channels(enabled_only=True):
            # Only consider channels with a valid expiration date
            if channel.token_expires_at:
                # Check if token is expired or expiring within the threshold
                if channel.token_expires_at <= threshold:
                    expiring_channels.append(channel.name)
        return expiring_channels
    
    def export_config(self) -> Dict[str, Any]:
        """Export current configuration for config.yaml compatibility."""
        config = {
            'accounts': {
                'youtube': []
            }
        }
        
        for channel in self.get_all_channels():
            # Get OAuth credentials from google_consoles table via console_name
            # Fallback to deprecated channel.client_id/client_secret
            credentials = self.get_console_credentials_for_channel(channel.name)
            
            if credentials:
                client_id = credentials['client_id']
                client_secret = credentials['client_secret']
                credentials_file = credentials.get('credentials_file', 'credentials.json')
            else:
                client_id = channel.client_id or ''
                client_secret = channel.client_secret or ''
                credentials_file = 'credentials.json'
            
            config['accounts']['youtube'].append({
                'name': channel.name,
                'channel_id': channel.channel_id,
                'console_name': channel.console_name,
                'client_id': client_id,
                'client_secret': client_secret,
                'credentials_file': credentials_file,
                'enabled': channel.enabled
            })
        
        return config
    
    def import_from_config(self, config: Dict[str, Any]) -> int:
        """Import channels from config.yaml format."""
        imported_count = 0
        youtube_accounts = config.get('accounts', {}).get('youtube', [])
        
        for account in youtube_accounts:
            if self.add_channel(
                name=account.get('name'),
                channel_id=account.get('channel_id', ''),
                client_id=account.get('client_id', ''),
                client_secret=account.get('client_secret', ''),
                enabled=account.get('enabled', True)
            ):
                imported_count += 1
        
        return imported_count
    
    # ==================== Google Console Methods ====================
    
    def add_google_console(self, name: str, client_id: str, client_secret: str,
                          credentials_file: Optional[str] = None,
                          description: Optional[str] = None,
                          enabled: bool = True) -> bool:
        """Add a new Google Cloud Console configuration.
        
        Args:
            name: Unique name for the console (used as identifier)
            client_id: OAuth Client ID from Google Cloud Console
            client_secret: OAuth Client Secret from Google Cloud Console
            credentials_file: Path to credentials.json file (optional)
            description: Optional description
            enabled: Whether console is enabled
        """
        try:
            query = """
                INSERT INTO google_consoles 
                (name, client_id, client_secret, credentials_file, description, enabled)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (name, client_id, client_secret, credentials_file, description, enabled))
            return True
        except Error as e:
            if e.errno == 1062:  # Duplicate entry
                return False
            raise
    
    def get_google_console(self, name: str) -> Optional[GoogleConsole]:
        """Get Google Console by name."""
        query = """
            SELECT id, name, client_id, client_secret, credentials_file, description,
                   enabled, created_at, updated_at
            FROM google_consoles WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        
        if results:
            row = results[0]
            return GoogleConsole(
                id=row[0],
                name=row[1],
                client_id=row[2],
                client_secret=row[3],
                credentials_file=row[4],
                description=row[5],
                enabled=bool(row[6]),
                created_at=row[7],
                updated_at=row[8]
            )
        return None
    
    def get_all_google_consoles(self, enabled_only: bool = False) -> List[GoogleConsole]:
        """Get all Google Console configurations."""
        if enabled_only:
            query = """
                SELECT id, name, client_id, client_secret, credentials_file, description,
                       enabled, created_at, updated_at
                FROM google_consoles WHERE enabled = 1
            """
        else:
            query = """
                SELECT id, name, client_id, client_secret, credentials_file, description,
                       enabled, created_at, updated_at
                FROM google_consoles
            """
        
        results = self._execute_query(query, fetch=True)
        consoles = []
        
        for row in results:
            consoles.append(GoogleConsole(
                id=row[0],
                name=row[1],
                client_id=row[2],
                client_secret=row[3],
                credentials_file=row[4],
                description=row[5],
                enabled=bool(row[6]),
                created_at=row[7],
                updated_at=row[8]
            ))
        
        return consoles
    
    def update_google_console(self, name: str, client_id: Optional[str] = None,
                              client_secret: Optional[str] = None,
                              credentials_file: Optional[str] = None,
                              description: Optional[str] = None,
                              enabled: Optional[bool] = None) -> bool:
        """Update Google Console configuration."""
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
            
            query = f"UPDATE google_consoles SET {', '.join(updates)} WHERE name = %s"
            self._execute_query(query, tuple(params))
            return True
        except Error:
            return False
    
    def delete_google_console(self, name: str) -> bool:
        """Delete a Google Console configuration."""
        try:
            query = "DELETE FROM google_consoles WHERE name = %s"
            self._execute_query(query, (name,))
            return True
        except Error:
            return False
    
    def get_console_credentials_for_channel(self, channel_name: str) -> Optional[Dict[str, str]]:
        """Get OAuth credentials for a channel from its associated Google Console.
        
        Priority:
        1. console_name (if set) -> get from google_consoles by name
        2. console_id (if set) -> get from google_consoles by id
        3. Fallback to deprecated channel.client_id/client_secret
        
        Returns:
            Dict with 'client_id', 'client_secret', and 'credentials_file' if found,
            None if channel or console not found
        """
        channel = self.get_channel(channel_name)
        if not channel:
            return None
        
        # Priority 1: If channel has console_name, get credentials from google_consoles by name
        if channel.console_name:
            console = self.get_google_console(channel.console_name)
            if console and console.enabled:
                return {
                    'client_id': console.client_id,
                    'client_secret': console.client_secret,
                    'credentials_file': console.credentials_file or 'credentials.json'
                }
        
        # Priority 2: If channel has console_id, get credentials from google_consoles by id
        if channel.console_id:
            console = self.get_console(channel.console_id)
            if console and console.enabled:
                return {
                    'client_id': console.client_id,
                    'client_secret': console.client_secret,
                    'credentials_file': console.credentials_file or 'credentials.json'
                }
        
        # Priority 3: Fallback to deprecated channel.client_id/client_secret for backward compatibility
        if channel.client_id and channel.client_secret:
            return {
                'client_id': channel.client_id,
                'client_secret': channel.client_secret,
                'credentials_file': 'credentials.json'
            }
        
        return None
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            # Get channel count
            channel_count = self._execute_query("SELECT COUNT(*) FROM youtube_channels", fetch=True)[0][0]
            enabled_count = self._execute_query("SELECT COUNT(*) FROM youtube_channels WHERE enabled = 1", fetch=True)[0][0]
            
            # Get token count
            token_count = self._execute_query("SELECT COUNT(*) FROM youtube_tokens", fetch=True)[0][0]
            
            # Get expired tokens count
            expired_count = len(self.get_expired_tokens())
            
            # Get Google Console count
            try:
                console_count = self._execute_query("SELECT COUNT(*) FROM google_consoles", fetch=True)[0][0]
            except (Error, IndexError, TypeError):
                console_count = 0
            
            # Get task stats
            try:
                task_count = self._execute_query("SELECT COUNT(*) FROM tasks", fetch=True)[0][0]
                pending_count = self._execute_query("SELECT COUNT(*) FROM tasks WHERE status = 0", fetch=True)[0][0]
                completed_count = self._execute_query("SELECT COUNT(*) FROM tasks WHERE status = 1", fetch=True)[0][0]
                failed_count = self._execute_query("SELECT COUNT(*) FROM tasks WHERE status = 2", fetch=True)[0][0]
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
            print(f"❌ Error getting database stats: {e}")
            return {}

    # ==================== Credential Management ====================

    def upsert_account_credentials(
        self,
        channel_name: str,
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
        """Create or update stored credentials for an automation channel.

        Args:
            channel_name: Linked YouTube channel name.
            login_email: Google account email.
            login_password: Google account password in raw form.
            totp_secret: Optional TOTP seed for MFA.
            backup_codes: Optional list of backup codes.
            proxy_host: Optional proxy hostname.
            proxy_port: Optional proxy port.
            proxy_username: Optional proxy username.
            proxy_password: Optional proxy password.
            profile_path: Optional Chromium profile path.
            user_agent: Optional custom user-agent string.
            enabled: Whether automation should use this credential.

        Returns:
            True if credentials were inserted or updated.
        """
        try:
            backup_codes_json = json.dumps(backup_codes) if backup_codes else None
            query = """
                INSERT INTO youtube_account_credentials (
                    channel_name,
                    login_email,
                    login_password,
                    totp_secret,
                    backup_codes,
                    proxy_host,
                    proxy_port,
                    proxy_username,
                    proxy_password,
                    profile_path,
                    user_agent,
                    enabled
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
                channel_name,
                login_email,
                login_password,
                totp_secret,
                backup_codes_json,
                proxy_host,
                proxy_port,
                proxy_username,
                proxy_password,
                profile_path,
                user_agent,
                enabled
            )
            self._execute_query(query, params)
            return True
        except Error as e:
            print(f"❌ Error upserting credentials for '{channel_name}': {e}")
            return False

    def disable_account_credentials(self, channel_name: str) -> bool:
        """Disable stored credentials for the specified channel."""
        try:
            query = """
                UPDATE youtube_account_credentials
                SET enabled = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE channel_name = %s
            """
            self._execute_query(query, (channel_name,))
            return True
        except Error as e:
            print(f"❌ Error disabling credentials for '{channel_name}': {e}")
            return False

    def get_account_credentials(
        self,
        channel_name: str,
        include_disabled: bool = False
    ) -> Optional[YouTubeAccountCredential]:
        """Fetch automation credentials for the channel."""
        try:
            query = """
                SELECT
                    id,
                    channel_name,
                    login_email,
                    login_password,
                    totp_secret,
                    backup_codes,
                    proxy_host,
                    proxy_port,
                    proxy_username,
                    proxy_password,
                    profile_path,
                    user_agent,
                    last_success_at,
                    last_attempt_at,
                    last_error,
                    enabled,
                    created_at,
                    updated_at
                FROM youtube_account_credentials
                WHERE channel_name = %s
            """
            if not include_disabled:
                query += " AND enabled = TRUE"
            results = self._execute_query(query, (channel_name,), fetch=True)
            if not results:
                return None
            return self._row_to_credentials(results[0])
        except Error as e:
            print(f"❌ Error fetching credentials for '{channel_name}': {e}")
            return None

    def list_account_credentials(self, limit: Optional[int] = None) -> List[YouTubeAccountCredential]:
        """List stored credentials."""
        try:
            query = """
                SELECT
                    id,
                    channel_name,
                    login_email,
                    login_password,
                    totp_secret,
                    backup_codes,
                    proxy_host,
                    proxy_port,
                    proxy_username,
                    proxy_password,
                    profile_path,
                    user_agent,
                    last_success_at,
                    last_attempt_at,
                    last_error,
                    enabled,
                    created_at,
                    updated_at
                FROM youtube_account_credentials
                ORDER BY channel_name ASC
            """
            if limit:
                results = self._execute_query(query + " LIMIT %s", (limit,), fetch=True)
            else:
                results = self._execute_query(query, fetch=True)
            return [self._row_to_credentials(row) for row in results]
        except Error as e:
            print(f"❌ Error listing credentials: {e}")
            return []

    def mark_credentials_attempt(
        self,
        channel_name: str,
        success: bool,
        error_message: Optional[str] = None,
        attempt_time: Optional[datetime] = None
    ) -> bool:
        """Update credential metadata after an automation attempt."""
        try:
            attempt_time = attempt_time or datetime.now()
            query = """
                UPDATE youtube_account_credentials
                SET
                    last_attempt_at = %s,
                    last_success_at = CASE WHEN %s THEN %s ELSE last_success_at END,
                    last_error = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE channel_name = %s
            """
            params = (
                attempt_time,
                success,
                attempt_time if success else None,
                None if success else error_message,
                channel_name
            )
            self._execute_query(query, params)
            return True
        except Error as e:
            print(f"❌ Error updating credentials attempt for '{channel_name}': {e}")
            return False
    
    def update_profile_path(self, channel_name: str, profile_path: str) -> bool:
        """Update profile_path for a channel's credentials.
        
        Args:
            channel_name: Name of the channel
            profile_path: Path to the browser profile directory
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            query = """
                UPDATE youtube_account_credentials
                SET profile_path = %s, updated_at = CURRENT_TIMESTAMP
                WHERE channel_name = %s
            """
            self._execute_query(query, (profile_path, channel_name))
            return True
        except Error as e:
            print(f"❌ Error updating profile_path for '{channel_name}': {e}")
            return False

    # ==================== Re-auth Audit ====================

    def create_reauth_audit(
        self,
        channel_name: str,
        status: str,
        initiated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """Create an audit record for an automation attempt."""
        try:
            initiated_at = initiated_at or datetime.now()
            metadata_json = json.dumps(metadata) if metadata else None
            query = """
                INSERT INTO youtube_reauth_audit (
                    channel_name,
                    initiated_at,
                    status,
                    metadata
                )
                VALUES (%s, %s, %s, %s)
            """
            self._execute_query(query, (channel_name, initiated_at, status, metadata_json))
            result = self._execute_query("SELECT LAST_INSERT_ID()", fetch=True)
            return result[0][0] if result else None
        except Error as e:
            print(f"❌ Error creating reauth audit for '{channel_name}': {e}")
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
                UPDATE youtube_reauth_audit
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
            print(f"❌ Error completing reauth audit #{audit_id}: {e}")
            return False

    def get_recent_reauth_audit(
        self,
        channel_name: str,
        limit: int = 10
    ) -> List[YouTubeReauthAudit]:
        """Retrieve recent audit entries for a channel."""
        try:
            query = """
                SELECT
                    id,
                    channel_name,
                    initiated_at,
                    completed_at,
                    status,
                    error_message,
                    metadata
                FROM youtube_reauth_audit
                WHERE channel_name = %s
                ORDER BY initiated_at DESC
                LIMIT %s
            """
            results = self._execute_query(query, (channel_name, limit), fetch=True)
            return [self._row_to_audit(row) for row in results]
        except Error as e:
            print(f"❌ Error fetching reauth audit for '{channel_name}': {e}")
            return []
    
    # ==================== Task Management Methods ====================
    
    def create_task(self, account_id: int, att_file_path: str, title: str,
                   date_post: datetime, media_type: str = 'youtube',
                   cover: Optional[str] = None, description: Optional[str] = None,
                   keywords: Optional[str] = None, post_comment: Optional[str] = None,
                   add_info: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """Create a new task."""
        try:
            add_info_json = json.dumps(add_info) if add_info else None
            
            query = """
                INSERT INTO tasks 
                (account_id, media_type, att_file_path, cover, title, description, 
                 keywords, post_comment, add_info, date_post)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (
                account_id, media_type, att_file_path, cover, title, 
                description, keywords, post_comment, add_info_json, date_post
            ))
            
            # Get the last inserted ID
            result = self._execute_query("SELECT LAST_INSERT_ID()", fetch=True)
            return result[0][0] if result else None
            
        except Error as e:
            print(f"❌ Error creating task: {e}")
            return None
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """Get task by ID."""
        query = """
            SELECT id, account_id, media_type, status, date_add, att_file_path,
                   cover, title, description, keywords, post_comment, add_info,
                   date_post, date_done, upload_id
            FROM tasks WHERE id = %s
        """
        results = self._execute_query(query, (task_id,), fetch=True)
        
        if results:
            row = results[0]
            return self._row_to_task(row)
        return None
    
    def get_pending_tasks(self, limit: Optional[int] = None) -> List[Task]:
        """Get all pending tasks that are ready to be executed."""
        query = """
            SELECT id, account_id, media_type, status, date_add, att_file_path,
                   cover, title, description, keywords, post_comment, add_info,
                   date_post, date_done, upload_id
            FROM tasks 
            WHERE status = 0 AND date_post <= NOW()
            ORDER BY date_post ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        
        results = self._execute_query(query, fetch=True)
        return [self._row_to_task(row) for row in results]
    
    def get_all_tasks(self, status: Optional[int] = None, 
                     account_id: Optional[int] = None,
                     limit: Optional[int] = None) -> List[Task]:
        """Get all tasks with optional filtering."""
        query = """
            SELECT id, account_id, media_type, status, date_add, att_file_path,
                   cover, title, description, keywords, post_comment, add_info,
                   date_post, date_done, upload_id
            FROM tasks WHERE 1=1
        """
        params = []
        
        if status is not None:
            query += " AND status = %s"
            params.append(status)
        
        if account_id is not None:
            query += " AND account_id = %s"
            params.append(account_id)
        
        query += " ORDER BY date_post DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = self._execute_query(query, tuple(params) if params else None, fetch=True)
        return [self._row_to_task(row) for row in results]
    
    def update_task_status(self, task_id: int, status: int, 
                          error_message: Optional[str] = None,
                          date_done: Optional[datetime] = None) -> bool:
        """Update task status."""
        try:
            if date_done is None and status == 1:  # Completed
                date_done = datetime.now()
            
            # Always try to update with error_message (column should exist after migration)
            query = """
                UPDATE tasks 
                SET status = %s, date_done = %s, error_message = %s
                WHERE id = %s
            """
            self._execute_query(query, (status, date_done, error_message, task_id))
            
            return True
        except Error as e:
            # If error_message column doesn't exist, try without it
            if 'error_message' in str(e).lower():
                try:
                    query = """
                        UPDATE tasks 
                        SET status = %s, date_done = %s
                        WHERE id = %s
                    """
                    self._execute_query(query, (status, date_done, task_id))
                    print("⚠️  Warning: error_message column not found, update without it")
                    return True
                except Error as e2:
                    print(f"❌ Error updating task status: {e2}")
                    return False
            else:
                print(f"❌ Error updating task status: {e}")
                return False
    
    def mark_task_processing(self, task_id: int) -> bool:
        """Mark task as processing."""
        return self.update_task_status(task_id, 3)
    
    def mark_task_completed(self, task_id: int, upload_id: Optional[str] = None) -> bool:
        """Mark task as completed and optionally save upload_id."""
        try:
            date_done = datetime.now()
            query = """
                UPDATE tasks 
                SET status = %s, date_done = %s, upload_id = %s
                WHERE id = %s
            """
            self._execute_query(query, (1, date_done, upload_id, task_id))
            return True
        except Error as e:
            print(f"❌ Error marking task completed: {e}")
            return False
    
    def mark_task_failed(self, task_id: int, error_message: str = None) -> bool:
        """Mark task as failed and store error message."""
        return self.update_task_status(task_id, 2, error_message=error_message)
    
    def update_task_upload_id(self, task_id: int, upload_id: str) -> bool:
        """Update task with upload_id after successful upload."""
        try:
            query = """
                UPDATE tasks 
                SET upload_id = %s
                WHERE id = %s
            """
            self._execute_query(query, (upload_id, task_id))
            return True
        except Error as e:
            print(f"❌ Error updating task upload_id: {e}")
            return False
    
    def increment_task_retry(self, _task_id: int) -> bool:
        """Increment task retry count (in memory only, not in DB)."""
        # retry_count тільки в пам'яті Task Worker
        return True
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        try:
            query = "DELETE FROM tasks WHERE id = %s"
            self._execute_query(query, (task_id,))
            return True
        except Error:
            return False
    
    def _row_to_credentials(self, row: tuple) -> YouTubeAccountCredential:
        """Convert database row to YouTubeAccountCredential."""
        backup_codes = None
        if row[5]:
            try:
                backup_codes = json.loads(row[5])
            except (json.JSONDecodeError, TypeError):
                backup_codes = None
        return YouTubeAccountCredential(
            id=row[0],
            channel_name=row[1],
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

    def _row_to_audit(self, row: tuple) -> YouTubeReauthAudit:
        """Convert database row to YouTubeReauthAudit."""
        metadata = None
        if row[6]:
            try:
                metadata = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                metadata = None
        return YouTubeReauthAudit(
            id=row[0],
            channel_name=row[1],
            initiated_at=row[2],
            completed_at=row[3],
            status=row[4],
            error_message=row[5],
            metadata=metadata
        )

    def _row_to_task(self, row: tuple) -> Task:
        """Convert database row to Task object."""
        add_info = None
        if row[11]:  # add_info field
            try:
                add_info = json.loads(row[11])
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Get error_message if column exists (position 15)
        error_message = None
        if len(row) > 15:
            error_message = row[15]
        
        return Task(
            id=row[0],
            account_id=row[1],
            media_type=row[2],
            status=row[3],
            date_add=row[4],
            att_file_path=row[5],
            cover=row[6],
            title=row[7],
            description=row[8],
            keywords=row[9],
            post_comment=row[10],
            add_info=add_info,
            date_post=row[12],
            date_done=row[13],
            upload_id=row[14] if len(row) > 14 else None,
            error_message=error_message,
            retry_count=0  # Не зберігаємо в БД
        )
    
    # ==================== Google Console Management ====================
    
    def add_console(self, name: str, client_id: str, client_secret: str,
                   project_id: Optional[str] = None,
                   credentials_file: Optional[str] = None,
                   redirect_uris: Optional[List[str]] = None,
                   description: Optional[str] = None,
                   enabled: bool = True) -> bool:
        """Add a new Google Cloud Console project."""
        try:
            redirect_uris_json = json.dumps(redirect_uris) if redirect_uris else None
            query = """
                INSERT INTO google_consoles 
                (name, project_id, client_id, client_secret, credentials_file, redirect_uris, description, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            self._execute_query(query, (name, project_id, client_id, client_secret, credentials_file, redirect_uris_json, description, enabled))
            return True
        except Error as e:
            if e.errno == 1062:  # Duplicate entry
                return False
            raise
    
    def get_console(self, console_id: int) -> Optional[GoogleConsole]:
        """Get console by ID."""
        query = """
            SELECT id, name, project_id, client_id, client_secret, credentials_file,
                   redirect_uris, description, enabled, created_at, updated_at
            FROM google_consoles WHERE id = %s
        """
        results = self._execute_query(query, (console_id,), fetch=True)
        
        if results:
            row = results[0]
            redirect_uris = None
            if row[6]:  # redirect_uris
                try:
                    redirect_uris = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                except (json.JSONDecodeError, TypeError):
                    redirect_uris = None
            return GoogleConsole(
                id=row[0],
                name=row[1],
                project_id=row[2],
                client_id=row[3],
                client_secret=row[4],
                credentials_file=row[5],
                redirect_uris=redirect_uris,
                description=row[7],
                enabled=bool(row[8]),
                created_at=row[9],
                updated_at=row[10]
            )
        return None
    
    def get_console_by_name(self, name: str) -> Optional[GoogleConsole]:
        """Get console by name."""
        query = """
            SELECT id, name, project_id, client_id, client_secret, credentials_file,
                   redirect_uris, description, enabled, created_at, updated_at
            FROM google_consoles WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        
        if results:
            row = results[0]
            redirect_uris = None
            if row[6]:  # redirect_uris
                try:
                    redirect_uris = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                except (json.JSONDecodeError, TypeError):
                    redirect_uris = None
            return GoogleConsole(
                id=row[0],
                name=row[1],
                project_id=row[2],
                client_id=row[3],
                client_secret=row[4],
                credentials_file=row[5],
                redirect_uris=redirect_uris,
                description=row[7],
                enabled=bool(row[8]),
                created_at=row[9],
                updated_at=row[10]
            )
        return None
    
    def get_all_consoles(self, enabled_only: bool = False) -> List[GoogleConsole]:
        """Get all Google Cloud Console projects."""
        if enabled_only:
            query = """
                SELECT id, name, project_id, client_id, client_secret, credentials_file,
                       redirect_uris, description, enabled, created_at, updated_at
                FROM google_consoles WHERE enabled = 1
            """
        else:
            query = """
                SELECT id, name, project_id, client_id, client_secret, credentials_file,
                       redirect_uris, description, enabled, created_at, updated_at
                FROM google_consoles
            """
        
        results = self._execute_query(query, fetch=True)
        consoles = []
        
        for row in results:
            redirect_uris = None
            if row[6]:  # redirect_uris
                try:
                    redirect_uris = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                except (json.JSONDecodeError, TypeError):
                    redirect_uris = None
            consoles.append(GoogleConsole(
                id=row[0],
                name=row[1],
                project_id=row[2],
                client_id=row[3],
                client_secret=row[4],
                credentials_file=row[5],
                redirect_uris=redirect_uris,
                description=row[7],
                enabled=bool(row[8]),
                created_at=row[9],
                updated_at=row[10]
            ))
        
        return consoles
    
    def update_channel_console(self, channel_name: str, console_id: Optional[int]) -> bool:
        """Update console_id for a channel."""
        try:
            query = """
                UPDATE youtube_channels 
                SET console_id = %s, updated_at = NOW()
                WHERE name = %s
            """
            self._execute_query(query, (console_id, channel_name))
            return True
        except Error:
            return False
    
    def get_console_for_channel(self, channel_name: str) -> Optional[GoogleConsole]:
        """Get the Google Console associated with a channel."""
        channel = self.get_channel(channel_name)
        if not channel or not channel.console_id:
            return None
        return self.get_console(channel.console_id)
    
    def close(self):
        """Close database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("✅ MySQL connection closed")


# Global database instance
_mysql_db_instance = None

def get_mysql_database(config: Dict[str, Any] = None) -> YouTubeMySQLDatabase:
    """Get global MySQL database instance."""
    global _mysql_db_instance
    if _mysql_db_instance is None:
        _mysql_db_instance = YouTubeMySQLDatabase(config)
    return _mysql_db_instance
