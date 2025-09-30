#!/usr/bin/env python3
"""
Database module for managing YouTube channels and tokens.
"""

import sqlite3
import json
import os
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


class YouTubeDatabase:
    """Database manager for YouTube channels and tokens."""
    
    def __init__(self, db_path: str = "youtube_channels.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create channels table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS youtube_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    channel_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    client_secret TEXT NOT NULL,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expires_at TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create tokens table for additional token storage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS youtube_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_name TEXT NOT NULL,
                    token_type TEXT NOT NULL,
                    token_value TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_name) REFERENCES youtube_channels (name)
                )
            """)
            
            conn.commit()
    
    def add_channel(self, name: str, channel_id: str, client_id: str, 
                   client_secret: str, enabled: bool = True) -> bool:
        """Add a new YouTube channel."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO youtube_channels 
                    (name, channel_id, client_id, client_secret, enabled)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, channel_id, client_id, client_secret, enabled))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Channel already exists
    
    def get_channel(self, name: str) -> Optional[YouTubeChannel]:
        """Get channel by name."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, channel_id, client_id, client_secret,
                       access_token, refresh_token, token_expires_at,
                       enabled, created_at, updated_at
                FROM youtube_channels WHERE name = ?
            """, (name,))
            
            row = cursor.fetchone()
            if row:
                return YouTubeChannel(
                    id=row[0],
                    name=row[1],
                    channel_id=row[2],
                    client_id=row[3],
                    client_secret=row[4],
                    access_token=row[5],
                    refresh_token=row[6],
                    token_expires_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    enabled=bool(row[8]),
                    created_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    updated_at=datetime.fromisoformat(row[10]) if row[10] else None
                )
            return None
    
    def get_all_channels(self, enabled_only: bool = False) -> List[YouTubeChannel]:
        """Get all channels."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if enabled_only:
                cursor.execute("""
                    SELECT id, name, channel_id, client_id, client_secret,
                           access_token, refresh_token, token_expires_at,
                           enabled, created_at, updated_at
                    FROM youtube_channels WHERE enabled = 1
                """)
            else:
                cursor.execute("""
                    SELECT id, name, channel_id, client_id, client_secret,
                           access_token, refresh_token, token_expires_at,
                           enabled, created_at, updated_at
                    FROM youtube_channels
                """)
            
            channels = []
            for row in cursor.fetchall():
                channels.append(YouTubeChannel(
                    id=row[0],
                    name=row[1],
                    channel_id=row[2],
                    client_id=row[3],
                    client_secret=row[4],
                    access_token=row[5],
                    refresh_token=row[6],
                    token_expires_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    enabled=bool(row[8]),
                    created_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    updated_at=datetime.fromisoformat(row[10]) if row[10] else None
                ))
            return channels
    
    def update_channel_tokens(self, name: str, access_token: str, 
                            refresh_token: Optional[str] = None,
                            expires_at: Optional[datetime] = None) -> bool:
        """Update channel tokens."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE youtube_channels 
                    SET access_token = ?, refresh_token = ?, 
                        token_expires_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (access_token, refresh_token, 
                     expires_at.isoformat() if expires_at else None, name))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE youtube_channels 
                    SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (enabled, name))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def delete_channel(self, name: str) -> bool:
        """Delete a channel."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM youtube_channels WHERE name = ?", (name,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def remove_channel(self, name: str) -> bool:
        """Remove a channel from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM youtube_channels WHERE name = ?", (name,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
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


# Global database instance
_db_instance = None

def get_database() -> YouTubeDatabase:
    """Get global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = YouTubeDatabase()
    return _db_instance
