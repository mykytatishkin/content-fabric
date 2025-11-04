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
class YouTubeChannel:
    """YouTube channel data structure."""
    id: int
    name: str
    channel_id: str
    client_id: str
    client_secret: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class Task:
    """Task data structure for scheduled posting."""
    id: int
    account_id: int
    media_type: str
    status: int  # 0=pending, 1=completed, 2=failed, 3=processing
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
    
    def add_channel(self, name: str, channel_id: str, client_id: str, 
                   client_secret: str, enabled: bool = True) -> bool:
        """Add a new YouTube channel."""
        try:
            query = """
                INSERT INTO youtube_channels 
                (name, channel_id, client_id, client_secret, enabled)
                VALUES (%s, %s, %s, %s, %s)
            """
            self._execute_query(query, (name, channel_id, client_id, client_secret, enabled))
            return True
        except Error as e:
            if e.errno == 1062:  # Duplicate entry
                return False
            raise
    
    def get_channel(self, name: str) -> Optional[YouTubeChannel]:
        """Get channel by name."""
        query = """
            SELECT id, name, channel_id, client_id, client_secret,
                   access_token, refresh_token, token_expires_at,
                   enabled, created_at, updated_at
            FROM youtube_channels WHERE name = %s
        """
        results = self._execute_query(query, (name,), fetch=True)
        
        if results:
            row = results[0]
            return YouTubeChannel(
                id=row[0],
                name=row[1],
                channel_id=row[2],
                client_id=row[3],
                client_secret=row[4],
                access_token=row[5],
                refresh_token=row[6],
                token_expires_at=row[7],
                enabled=bool(row[8]),
                created_at=row[9],
                updated_at=row[10]
            )
        return None
    
    def get_all_channels(self, enabled_only: bool = False) -> List[YouTubeChannel]:
        """Get all channels."""
        if enabled_only:
            query = """
                SELECT id, name, channel_id, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       enabled, created_at, updated_at
                FROM youtube_channels WHERE enabled = 1
            """
        else:
            query = """
                SELECT id, name, channel_id, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       enabled, created_at, updated_at
                FROM youtube_channels
            """
        
        results = self._execute_query(query, fetch=True)
        channels = []
        
        for row in results:
            channels.append(YouTubeChannel(
                id=row[0],
                name=row[1],
                channel_id=row[2],
                client_id=row[3],
                client_secret=row[4],
                access_token=row[5],
                refresh_token=row[6],
                token_expires_at=row[7],
                enabled=bool(row[8]),
                created_at=row[9],
                updated_at=row[10]
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
        """Check if channel token is expired."""
        channel = self.get_channel(name)
        if not channel or not channel.token_expires_at:
            return True
        return datetime.now() >= channel.token_expires_at
    
    def get_expired_tokens(self) -> List[str]:
        """Get list of channels with expired tokens."""
        expired_channels = []
        for channel in self.get_all_channels(enabled_only=True):
            if self.is_token_expired(channel.name):
                expired_channels.append(channel.name)
        return expired_channels
    
    def export_config(self) -> Dict[str, Any]:
        """Export current configuration for config.yaml compatibility."""
        config = {
            'accounts': {
                'youtube': []
            }
        }
        
        for channel in self.get_all_channels():
            config['accounts']['youtube'].append({
                'name': channel.name,
                'channel_id': channel.channel_id,
                'client_id': channel.client_id,
                'client_secret': channel.client_secret,
                'credentials_file': 'credentials.json',  # Single file for all
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
                'total_tasks': task_count,
                'pending_tasks': pending_count,
                'completed_tasks': completed_count,
                'failed_tasks': failed_count
            }
        except Error as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
    
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
            
            # Check if error_message column exists
            try:
                query = """
                    UPDATE tasks 
                    SET status = %s, date_done = %s, error_message = %s
                    WHERE id = %s
                """
                self._execute_query(query, (status, date_done, error_message, task_id))
            except Error:
                # Fallback if error_message column doesn't exist yet
                query = """
                    UPDATE tasks 
                    SET status = %s, date_done = %s
                    WHERE id = %s
                """
                self._execute_query(query, (status, date_done, task_id))
            
            return True
        except Error as e:
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
    
    def increment_task_retry(self, task_id: int) -> bool:
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
