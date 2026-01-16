"""
Logging configuration and utilities for the social media auto-posting system.
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


class SocialMediaLogger:
    """Centralized logging system for social media auto-posting."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            # Default configuration if file not found
            return {
                'logging': {
                    'level': 'INFO',
                    'file': './logs/auto_posting.log',
                    'max_size': '10MB',
                    'backup_count': 5,
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                }
            }
    
    def _setup_logger(self) -> logging.Logger:
        """Set up the main logger with file and console handlers."""
        logger = logging.getLogger('social_media_auto_poster')
        logger.setLevel(getattr(logging, self.config['logging']['level']))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create logs directory if it doesn't exist
        log_file = self.config['logging']['file']
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File handler with rotation
        max_bytes = self._parse_size(self.config['logging']['max_size'])
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=self.config['logging']['backup_count']
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler with colors
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, self.config['logging']['level']))
        
        # Formatters
        file_formatter = logging.Formatter(self.config['logging']['format'])
        console_formatter = ColoredFormatter(self.config['logging']['format'])
        
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes."""
        size_str = size_str.upper()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """Get a logger instance."""
        if name:
            return logging.getLogger(f'social_media_auto_poster.{name}')
        return self.logger
    
    def log_post_attempt(self, platform: str, account: str, content_path: str, 
                        scheduled_time: Optional[datetime] = None):
        """Log a post attempt."""
        time_str = scheduled_time.strftime('%Y-%m-%d %H:%M:%S') if scheduled_time else 'immediate'
        self.logger.info(f"Attempting to post to {platform} ({account}) at {time_str}: {content_path}")
    
    def log_post_success(self, platform: str, account: str, post_id: str, 
                        content_path: str, posted_at: datetime):
        """Log a successful post."""
        self.logger.info(f"✅ Successfully posted to {platform} ({account}) - Post ID: {post_id} at {posted_at}")
    
    def log_post_failure(self, platform: str, account: str, content_path: str, 
                        error: str, retry_count: int = 0):
        """Log a failed post attempt."""
        retry_info = f" (Retry {retry_count})" if retry_count > 0 else ""
        self.logger.error(f"❌ Failed to post to {platform} ({account}){retry_info}: {error}")
    
    def log_schedule_created(self, platform: str, account: str, content_path: str, 
                           scheduled_time: datetime):
        """Log a scheduled post creation."""
        self.logger.info(f"📅 Scheduled post for {platform} ({account}) at {scheduled_time}: {content_path}")
    
    def log_content_processing(self, input_path: str, output_path: str, 
                             platform: str, processing_time: float):
        """Log content processing completion."""
        self.logger.info(f"🎬 Processed content for {platform}: {input_path} -> {output_path} ({processing_time:.2f}s)")
    
    def log_api_error(self, platform: str, endpoint: str, status_code: int, 
                     error_message: str):
        """Log API-related errors."""
        self.logger.error(f"🔌 API Error - {platform} {endpoint}: {status_code} - {error_message}")
    
    def log_rate_limit(self, platform: str, reset_time: datetime):
        """Log rate limit hit."""
        self.logger.warning(f"⏰ Rate limit hit for {platform}. Reset at: {reset_time}")
    
    def log_configuration_loaded(self, config_path: str):
        """Log configuration loading."""
        self.logger.info(f"⚙️ Configuration loaded from: {config_path}")
    
    def log_account_validation(self, platform: str, account: str, is_valid: bool):
        """Log account validation results."""
        status = "✅ Valid" if is_valid else "❌ Invalid"
        self.logger.info(f"🔐 Account validation - {platform} ({account}): {status}")


# Global logger instance
logger_instance = SocialMediaLogger()
get_logger = logger_instance.get_logger
