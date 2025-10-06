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
            query = """
                UPDATE youtube_channels 
                SET access_token = %s, refresh_token = %s, 
                    token_expires_at = %s, updated_at = NOW()
                WHERE name = %s
            """
            self._execute_query(query, (access_token, refresh_token, expires_at, name))
            return True
        except Error:
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
            
            return {
                'total_channels': channel_count,
                'enabled_channels': enabled_count,
                'disabled_channels': channel_count - enabled_count,
                'total_tokens': token_count,
                'expired_tokens': expired_count
            }
        except Error as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
    
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
