"""
Database-based configuration loader for YouTube channels.
Replaces YAML-based account configuration with database storage.
"""

import os
from typing import Dict, Any, List, Optional
from .database import get_database, YouTubeChannel
from .config_loader import ConfigLoader
from .logger import get_logger


class DatabaseConfigLoader:
    """Configuration loader that reads YouTube channels from database instead of YAML."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.logger = get_logger("database_config_loader")
        self.db = get_database()
        
        # Load base config from YAML (platforms, schedule, etc.)
        self.yaml_loader = ConfigLoader(config_path)
        self.base_config = self.yaml_loader.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration with YouTube channels from database."""
        try:
            # Start with base YAML config
            config = self.base_config.copy()
            
            # Replace YouTube accounts with database data
            config['accounts']['youtube'] = self._load_youtube_channels_from_db()
            
            self.logger.info("Configuration loaded from database")
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading database configuration: {e}")
            return self.base_config
    
    def _load_youtube_channels_from_db(self) -> List[Dict[str, Any]]:
        """Load YouTube channels from database and convert to config format."""
        try:
            channels = self.db.get_all_channels(enabled_only=True)
            config_channels = []
            
            for channel in channels:
                # Get OAuth credentials from environment variables
                client_id = os.getenv('YOUTUBE_MAIN_CLIENT_ID', channel.client_id)
                client_secret = os.getenv('YOUTUBE_MAIN_CLIENT_SECRET', channel.client_secret)
                
                config_channel = {
                    'name': channel.name,
                    'channel_id': channel.channel_id,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'credentials_file': 'credentials.json',
                    'enabled': channel.enabled,
                    # Add database-specific fields
                    'db_id': channel.id,
                    'access_token': channel.access_token,
                    'refresh_token': channel.refresh_token,
                    'token_expires_at': channel.token_expires_at.isoformat() if channel.token_expires_at else None
                }
                config_channels.append(config_channel)
            
            self.logger.info(f"Loaded {len(config_channels)} YouTube channels from database")
            return config_channels
            
        except Exception as e:
            self.logger.error(f"Error loading YouTube channels from database: {e}")
            return []
    
    def add_youtube_channel(self, name: str, channel_id: str, 
                           client_id: Optional[str] = None, 
                           client_secret: Optional[str] = None,
                           enabled: bool = True) -> bool:
        """Add a new YouTube channel to database."""
        try:
            # Use environment variables if not provided
            if not client_id:
                client_id = os.getenv('YOUTUBE_MAIN_CLIENT_ID', '')
            if not client_secret:
                client_secret = os.getenv('YOUTUBE_MAIN_CLIENT_SECRET', '')
            
            success = self.db.add_channel(
                name=name,
                channel_id=channel_id,
                client_id=client_id,
                client_secret=client_secret,
                enabled=enabled
            )
            
            if success:
                self.logger.info(f"Added YouTube channel '{name}' to database")
            else:
                self.logger.warning(f"Failed to add YouTube channel '{name}' (may already exist)")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error adding YouTube channel '{name}': {e}")
            return False
    
    def remove_youtube_channel(self, name: str) -> bool:
        """Remove a YouTube channel from database."""
        try:
            success = self.db.remove_channel(name)
            if success:
                self.logger.info(f"Removed YouTube channel '{name}' from database")
            return success
        except Exception as e:
            self.logger.error(f"Error removing YouTube channel '{name}': {e}")
            return False
    
    def update_channel_tokens(self, name: str, access_token: str, 
                             refresh_token: Optional[str] = None,
                             expires_at: Optional[str] = None) -> bool:
        """Update channel tokens in database."""
        try:
            success = self.db.update_channel_tokens(
                name=name,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )
            if success:
                self.logger.info(f"Updated tokens for channel '{name}'")
            return success
        except Exception as e:
            self.logger.error(f"Error updating tokens for channel '{name}': {e}")
            return False
    
    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all YouTube channels."""
        try:
            channels = self.db.get_all_channels()
            status = {
                'total': len(channels),
                'enabled': len([c for c in channels if c.enabled]),
                'authorized': len([c for c in channels if c.access_token]),
                'valid_tokens': 0,
                'expired_tokens': 0,
                'channels': {}
            }
            
            for channel in channels:
                # Проверяем истечение токена
                is_expired = True
                if channel.access_token and channel.token_expires_at:
                    from datetime import datetime
                    now = datetime.now()
                    # Приводим к одному типу (timezone-naive)
                    if now.tzinfo is None and channel.token_expires_at.tzinfo is not None:
                        now = now.replace(tzinfo=channel.token_expires_at.tzinfo)
                    elif now.tzinfo is not None and channel.token_expires_at.tzinfo is None:
                        channel.token_expires_at = channel.token_expires_at.replace(tzinfo=now.tzinfo)
                    is_expired = now >= channel.token_expires_at
                
                if channel.access_token and not is_expired:
                    status['valid_tokens'] += 1
                elif channel.access_token and is_expired:
                    status['expired_tokens'] += 1
                
                status['channels'][channel.name] = {
                    'enabled': channel.enabled,
                    'authorized': bool(channel.access_token),
                    'token_valid': bool(channel.access_token and not is_expired),
                    'expires_at': channel.token_expires_at.isoformat() if channel.token_expires_at else None,
                    'created_at': channel.created_at.isoformat() if channel.created_at else None
                }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting channel status: {e}")
            return {'total': 0, 'enabled': 0, 'authorized': 0, 'valid_tokens': 0, 'expired_tokens': 0, 'channels': {}}
    
    def migrate_from_yaml(self) -> int:
        """Migrate YouTube channels from YAML config to database."""
        try:
            yaml_accounts = self.base_config.get('accounts', {}).get('youtube', [])
            migrated_count = 0
            
            for account in yaml_accounts:
                name = account.get('name')
                if not name:
                    continue
                
                # Check if channel already exists in database
                existing = self.db.get_channel(name)
                if existing:
                    self.logger.info(f"Channel '{name}' already exists in database, skipping")
                    continue
                
                # Add channel to database
                success = self.add_youtube_channel(
                    name=name,
                    channel_id=account.get('channel_id', ''),
                    client_id=account.get('client_id', ''),
                    client_secret=account.get('client_secret', ''),
                    enabled=account.get('enabled', True)
                )
                
                if success:
                    migrated_count += 1
            
            self.logger.info(f"Migrated {migrated_count} channels from YAML to database")
            return migrated_count
            
        except Exception as e:
            self.logger.error(f"Error migrating from YAML: {e}")
            return 0
