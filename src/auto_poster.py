"""
Main auto-posting system that coordinates all components.
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import yaml
import argparse

from .logger import get_logger
# from .content_processor import ContentProcessor  # отключено для упрощения
from .scheduler import PostingScheduler, ScheduledPost
from .notifications import NotificationManager
from .token_manager import TokenManager
from .oauth_manager import OAuthManager
from .config_loader import ConfigLoader
from .database_config_loader import DatabaseConfigLoader
from .api_clients.instagram_client import InstagramClient
from .api_clients.tiktok_client import TikTokClient
from .api_clients.youtube_client import YouTubeClient


class SocialMediaAutoPoster:
    """Main class that coordinates all components of the auto-posting system."""
    
    def __init__(self, config_path: str = "config.yaml", use_database: bool = True):
        self.config_path = config_path
        self.use_database = use_database
        self.config = self._load_config()
        self.logger = get_logger("auto_poster")
        
        # Initialize components (content_processor отключен для упрощения)
        # self.content_processor = ContentProcessor(config_path)
        self.scheduler = PostingScheduler(config_path)
        self.notification_manager = NotificationManager(config_path)
        self.token_manager = TokenManager(config_path)
        self.oauth_manager = OAuthManager(config_path)
        
        # Initialize API clients
        self.api_clients = self._initialize_api_clients()
        
        # Set up scheduler callback
        self.scheduler.set_posting_callback(self._posting_callback)
        
        self.logger.info("Social Media Auto-Poster initialized")
    
    def _load_config(self) -> dict:
        """Load configuration from YAML file or database with environment variables support."""
        try:
            if self.use_database:
                config_loader = DatabaseConfigLoader(self.config_path)
                return config_loader.load_config()
            else:
                config_loader = ConfigLoader(self.config_path)
                return config_loader.load_config()
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Configuration loading error: {str(e)}")
            sys.exit(1)
    
    def _initialize_api_clients(self) -> Dict[str, Any]:
        """Initialize API clients for each platform."""
        clients = {}
        
        # Instagram client
        if self.config.get('platforms', {}).get('instagram', {}).get('enabled', False):
            try:
                instagram_config = self.config.get('accounts', {}).get('instagram', [{}])[0]
                clients['instagram'] = InstagramClient(
                    app_id=instagram_config.get('app_id', ''),
                    app_secret=instagram_config.get('app_secret', '')
                )
                self.logger.info("Instagram client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Instagram client: {str(e)}")
        
        # TikTok client
        if self.config.get('platforms', {}).get('tiktok', {}).get('enabled', False):
            try:
                tiktok_config = self.config.get('accounts', {}).get('tiktok', [{}])[0]
                clients['tiktok'] = TikTokClient(
                    client_key=tiktok_config.get('client_key', ''),
                    client_secret=tiktok_config.get('client_secret', '')
                )
                self.logger.info("TikTok client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize TikTok client: {str(e)}")
        
        # YouTube client
        if self.config.get('platforms', {}).get('youtube', {}).get('enabled', False):
            try:
                youtube_config = self.config.get('accounts', {}).get('youtube', [{}])[0]
                clients['youtube'] = YouTubeClient(
                    client_id=youtube_config.get('client_id', ''),
                    client_secret=youtube_config.get('client_secret', ''),
                    credentials_file=youtube_config.get('credentials_file')
                )
                self.logger.info("YouTube client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize YouTube client: {str(e)}")
        
        return clients
    
    def _posting_callback(self, scheduled_post: ScheduledPost) -> Dict[str, Any]:
        """Callback function for scheduled posts."""
        try:
            self.logger.log_post_attempt(
                scheduled_post.platform, 
                scheduled_post.account, 
                scheduled_post.content_path,
                scheduled_post.scheduled_time
            )
            
            # Get API client for the platform
            client = self.api_clients.get(scheduled_post.platform)
            if not client:
                return {
                    'success': False,
                    'error': f'No API client available for {scheduled_post.platform}'
                }
            
            # Get account information
            account_info = self._get_account_info(scheduled_post.platform, scheduled_post.account)
            if not account_info:
                return {
                    'success': False,
                    'error': f'Account information not found for {scheduled_post.account}'
                }
            
            # Post the content
            result = client.post_video(
                account_info=account_info,
                video_path=scheduled_post.content_path,
                caption=scheduled_post.caption,
                metadata=scheduled_post.metadata
            )
            
            # Send notifications
            if result.success:
                self.notification_manager.send_success_notification(
                    scheduled_post.platform,
                    scheduled_post.account,
                    result.post_id,
                    scheduled_post.content_path,
                    result.posted_at
                )
            else:
                self.notification_manager.send_failure_notification(
                    scheduled_post.platform,
                    scheduled_post.account,
                    scheduled_post.content_path,
                    result.error_message,
                    scheduled_post.retry_count
                )
            
            return {
                'success': result.success,
                'post_id': result.post_id,
                'error': result.error_message
            }
            
        except Exception as e:
            self.logger.error(f"Posting callback error: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_account_info(self, platform: str, account_name: str) -> Optional[Dict[str, Any]]:
        """Get account information for a specific platform and account."""
        accounts = self.config.get('accounts', {}).get(platform, [])
        for account in accounts:
            if account.get('name') == account_name:
                # Обновить токен доступа из TokenManager
                token_info = self.token_manager.get_token(platform, account_name)
                if token_info:
                    account = account.copy()  # Создать копию, чтобы не изменить оригинал
                    account['access_token'] = token_info.access_token
                    if token_info.refresh_token:
                        account['refresh_token'] = token_info.refresh_token
                return account
        return None
    
    def post_immediately(self, content_path: str, platforms: List[str], 
                        caption: str, accounts: Optional[List[str]] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Post content immediately to specified platforms.
        
        Args:
            content_path: Path to the content file
            platforms: List of platforms to post to
            caption: Post caption
            accounts: List of account names (if None, uses all enabled accounts)
            metadata: Additional metadata
            
        Returns:
            Dictionary with posting results
        """
        results = {
            'successful_posts': 0,
            'failed_posts': 0,
            'results': []
        }
        
        try:
            # Используем готовый файл без обработки
            self.logger.info(f"Using ready content: {content_path}")
            
            # Проверяем, что файл существует
            if not os.path.exists(content_path):
                raise FileNotFoundError(f"Content file not found: {content_path}")
            
            # Post to each platform
            for platform in platforms:
                
                # Get accounts for this platform
                platform_accounts = self._get_platform_accounts(platform, accounts)
                
                for account in platform_accounts:
                    try:
                        # Get API client
                        client = self.api_clients.get(platform)
                        if not client:
                            raise Exception(f"No API client for {platform}")
                        
                        # Post the content (используем оригинальный файл)
                        result = client.post_video(
                            account_info=account,
                            video_path=content_path,
                            caption=caption,
                            metadata=metadata
                        )
                        
                        if result.success:
                            results['successful_posts'] += 1
                            self.notification_manager.send_success_notification(
                                platform, account['name'], result.post_id,
                                content_path, result.posted_at
                            )
                        else:
                            results['failed_posts'] += 1
                            self.notification_manager.send_failure_notification(
                                platform, account['name'], content_path,
                                result.error_message
                            )
                        
                        results['results'].append({
                            'platform': platform,
                            'account': account['name'],
                            'success': result.success,
                            'post_id': result.post_id,
                            'error': result.error_message
                        })
                        
                    except Exception as e:
                        results['failed_posts'] += 1
                        self.logger.error(f"Failed to post to {platform} ({account['name']}): {str(e)}")
                        results['results'].append({
                            'platform': platform,
                            'account': account['name'],
                            'success': False,
                            'error': str(e)
                        })
            
            # Send batch summary
            summary_data = {
                'total_posts': results['successful_posts'] + results['failed_posts'],
                'successful_posts': results['successful_posts'],
                'failed_posts': results['failed_posts'],
                'platforms': platforms
            }
            self.notification_manager.send_batch_summary(summary_data)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Immediate posting failed: {str(e)}")
            return {
                'successful_posts': 0,
                'failed_posts': 0,
                'error': str(e),
                'results': []
            }
    
    def schedule_post(self, content_path: str, platforms: List[str], 
                     caption: str, scheduled_time: Optional[datetime] = None,
                     accounts: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Schedule posts for specified platforms.
        
        Args:
            content_path: Path to the content file
            platforms: List of platforms to post to
            caption: Post caption
            scheduled_time: Specific time to post (if None, generates random time)
            accounts: List of account names (if None, uses all enabled accounts)
            metadata: Additional metadata
            
        Returns:
            List of scheduled post IDs
        """
        scheduled_post_ids = []
        
        try:
            # Используем готовый файл для планирования
            self.logger.info(f"Scheduling ready content: {content_path}")
            
            # Проверяем, что файл существует
            if not os.path.exists(content_path):
                raise FileNotFoundError(f"Content file not found: {content_path}")
            
            # Schedule posts for each platform
            for platform in platforms:
                
                # Get accounts for this platform
                platform_accounts = self._get_platform_accounts(platform, accounts)
                
                for account in platform_accounts:
                    post_id = self.scheduler.schedule_post(
                        platform=platform,
                        account=account['name'],
                        content_path=content_path,
                        caption=caption,
                        scheduled_time=scheduled_time,
                        metadata=metadata
                    )
                    scheduled_post_ids.append(post_id)
            
            self.logger.info(f"Scheduled {len(scheduled_post_ids)} posts")
            return scheduled_post_ids
            
        except Exception as e:
            self.logger.error(f"Scheduling failed: {str(e)}")
            return []
    
    def _get_platform_accounts(self, platform: str, account_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get accounts for a specific platform."""
        all_accounts = self.config.get('accounts', {}).get(platform, [])
        
        filtered_accounts = []
        if account_names is None:
            # Return all enabled accounts
            candidate_accounts = [acc for acc in all_accounts if acc.get('enabled', True)]
        else:
            # Return specified accounts
            candidate_accounts = [acc for acc in all_accounts if acc.get('name') in account_names and acc.get('enabled', True)]
        
        # Добавить аккаунты (токены уже загружены DatabaseConfigLoader)
        for account in candidate_accounts:
            account_name = account.get('name')
            if account_name:
                # Проверить наличие токенов
                if platform == 'youtube' and self.use_database:
                    # Для YouTube токены уже загружены DatabaseConfigLoader
                    if account.get('access_token'):
                        filtered_accounts.append(account)
                    else:
                        self.logger.warning(f"Нет токена для аккаунта {platform}:{account_name}")
                        filtered_accounts.append(account)
                else:
                    # Для других платформ использовать TokenManager
                    token_info = self.token_manager.get_token(platform, account_name)
                    if token_info:
                        account = account.copy()  # Создать копию
                        account['access_token'] = token_info.access_token
                        if token_info.refresh_token:
                            account['refresh_token'] = token_info.refresh_token
                        filtered_accounts.append(account)
                    else:
                        self.logger.warning(f"Нет токена для аккаунта {platform}:{account_name}")
                        filtered_accounts.append(account)
            else:
                filtered_accounts.append(account)
        
        return filtered_accounts
    
    def start_scheduler(self):
        """Start the posting scheduler."""
        self.scheduler.start_scheduler()
        self.logger.info("Auto-poster scheduler started")
    
    def stop_scheduler(self):
        """Stop the posting scheduler."""
        self.scheduler.stop_scheduler()
        self.logger.info("Auto-poster scheduler stopped")
    
    def validate_accounts(self) -> Dict[str, List[Dict[str, Any]]]:
        """Validate all configured accounts."""
        validation_results = {}
        
        for platform, client in self.api_clients.items():
            validation_results[platform] = []
            accounts = self.config.get('accounts', {}).get(platform, [])
            
            for account in accounts:
                if not account.get('enabled', True):
                    continue
                
                is_valid = client.validate_account(account)
                validation_results[platform].append({
                    'name': account.get('name', 'Unknown'),
                    'valid': is_valid
                })
                
                self.logger.log_account_validation(platform, account.get('name', 'Unknown'), is_valid)
        
        return validation_results
    
    def get_scheduled_posts(self, platform: Optional[str] = None, 
                          account: Optional[str] = None) -> List[ScheduledPost]:
        """Get scheduled posts with optional filtering."""
        return self.scheduler.get_scheduled_posts(platform, account)
    
    def cancel_post(self, post_id: str) -> bool:
        """Cancel a scheduled post."""
        return self.scheduler.cancel_post(post_id)
    
    def get_posting_stats(self) -> Dict[str, Any]:
        """Get posting statistics."""
        return self.scheduler.get_posting_stats()
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test notification channels."""
        return self.notification_manager.test_notifications()
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            'api_clients': {platform: client.test_connection() for platform, client in self.api_clients.items()},
            'scheduler_running': self.scheduler.running,
            'notification_status': self.notification_manager.get_notification_status(),
            'scheduled_posts_count': len(self.scheduler.scheduled_posts),
            'config_loaded': bool(self.config),
            'token_status': self.token_manager.get_token_status(),
            'account_status': self.oauth_manager.get_account_status()
        }
    
    def authorize_account(self, platform: str, account_name: str, 
                         custom_scopes: Optional[list] = None, 
                         auto_open_browser: bool = True) -> Dict[str, Any]:
        """Авторизовать конкретный аккаунт."""
        return self.oauth_manager.authorize_account(
            platform=platform,
            account_name=account_name,
            custom_scopes=custom_scopes,
            auto_open_browser=auto_open_browser
        )
    
    def authorize_all_accounts(self, platform: Optional[str] = None) -> Dict[str, Any]:
        """Авторизовать все аккаунты для платформы или всех платформ."""
        return self.oauth_manager.authorize_all_accounts(platform)
    
    def refresh_account_tokens(self, platform: Optional[str] = None, 
                              account_name: Optional[str] = None) -> Dict[str, Any]:
        """Обновить токены для аккаунтов."""
        results = {}
        
        if platform and account_name:
            # Обновить конкретный аккаунт
            success = self.token_manager.refresh_token_if_needed(platform, account_name)
            results[f"{platform}:{account_name}"] = success
        else:
            # Обновить все токены или для конкретной платформы
            all_tokens = self.token_manager.get_all_tokens(platform)
            
            for plat, accounts in all_tokens.items():
                for acc_name in accounts.keys():
                    success = self.token_manager.refresh_token_if_needed(plat, acc_name)
                    results[f"{plat}:{acc_name}"] = success
        
        return results
    
    def validate_all_accounts_extended(self) -> Dict[str, Any]:
        """Расширенная валидация всех аккаунтов с проверкой токенов."""
        validation_results = {}
        
        for platform, client in self.api_clients.items():
            validation_results[platform] = {}
            accounts = self.config.get('accounts', {}).get(platform, [])
            
            for account in accounts:
                account_name = account.get('name', 'Unknown')
                if not account.get('enabled', True):
                    validation_results[platform][account_name] = {
                        'enabled': False,
                        'valid': False,
                        'has_token': False,
                        'token_valid': False,
                        'error': 'Аккаунт отключен в конфигурации'
                    }
                    continue
                
                # Проверить наличие токена
                token_info = self.token_manager.get_token(platform, account_name)
                has_token = token_info is not None
                
                # Проверить валидность токена
                token_valid = False
                if has_token:
                    token_valid = not self.token_manager.is_token_expired(token_info)
                    if not token_valid:
                        # Попробовать обновить токен
                        token_valid = self.token_manager.refresh_token_if_needed(platform, account_name)
                
                # Проверить API соединение
                api_valid = False
                error_message = None
                
                if token_valid:
                    try:
                        # Обновить конфигурацию аккаунта с актуальным токеном
                        updated_account = account.copy()
                        updated_account['access_token'] = token_info.access_token
                        
                        api_valid = client.validate_account(updated_account)
                        if not api_valid:
                            error_message = "API валидация не прошла"
                    except Exception as e:
                        error_message = str(e)
                else:
                    error_message = "Нет действительного токена"
                
                validation_results[platform][account_name] = {
                    'enabled': True,
                    'valid': api_valid,
                    'has_token': has_token,
                    'token_valid': token_valid,
                    'error': error_message
                }
                
                self.logger.log_account_validation(platform, account_name, api_valid)
        
        return validation_results
    
    def get_account_authorization_url(self, platform: str, account_name: str, 
                                    custom_scopes: Optional[list] = None) -> Optional[str]:
        """Получить URL для ручной авторизации аккаунта."""
        return self.oauth_manager.get_authorization_url(platform, account_name, custom_scopes)
    
    def add_account_token(self, platform: str, account_name: str, access_token: str,
                         refresh_token: Optional[str] = None, expires_in: Optional[int] = None,
                         scope: Optional[str] = None) -> bool:
        """Добавить токен для аккаунта вручную."""
        return self.token_manager.add_token(
            platform=platform,
            account_name=account_name,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            scope=scope
        )
    
    def remove_account_token(self, platform: str, account_name: str) -> bool:
        """Удалить токен аккаунта."""
        return self.token_manager.remove_token(platform, account_name)
    
    def get_account_token_info(self, platform: str, account_name: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о токене аккаунта."""
        token_info = self.token_manager.get_token(platform, account_name)
        if not token_info:
            return None
        
        return {
            'platform': token_info.platform,
            'account_name': token_info.account_name,
            'has_refresh_token': bool(token_info.refresh_token),
            'expires_at': token_info.expires_at.isoformat() if token_info.expires_at else None,
            'scope': token_info.scope,
            'created_at': token_info.created_at.isoformat() if token_info.created_at else None,
            'last_refreshed': token_info.last_refreshed.isoformat() if token_info.last_refreshed else None,
            'is_expired': self.token_manager.is_token_expired(token_info)
        }

