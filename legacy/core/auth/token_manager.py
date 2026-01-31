"""
Система управления токенами и автоматического обновления для всех социальных платформ.
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import yaml
from pathlib import Path

from core.utils.logger import get_logger


@dataclass
class TokenInfo:
    """Информация о токене доступа."""
    platform: str
    account_name: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    created_at: Optional[datetime] = None
    last_refreshed: Optional[datetime] = None


class TokenManager:
    """Менеджер для управления токенами доступа всех платформ."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = get_logger("token_manager")
        self.tokens_file = "tokens.json"    
        self.tokens = self._load_tokens()
        
    def _load_config(self) -> dict:
        """Загрузить конфигурацию из YAML файла."""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            self.logger.error(f"Файл конфигурации не найден: {self.config_path}")
            return {}
    
    def _load_tokens(self) -> Dict[str, Dict[str, TokenInfo]]:
        """Загрузить сохраненные токены."""
        if not os.path.exists(self.tokens_file):
            return {}
        
        try:
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
            
            tokens = {}
            for platform, accounts in data.items():
                tokens[platform] = {}
                for account_name, token_data in accounts.items():
                    tokens[platform][account_name] = TokenInfo(
                        platform=token_data['platform'],
                        account_name=token_data['account_name'],
                        access_token=token_data['access_token'],
                        refresh_token=token_data.get('refresh_token'),
                        expires_at=datetime.fromisoformat(token_data['expires_at']) if token_data.get('expires_at') else None,
                        scope=token_data.get('scope'),
                        created_at=datetime.fromisoformat(token_data['created_at']) if token_data.get('created_at') else None,
                        last_refreshed=datetime.fromisoformat(token_data['last_refreshed']) if token_data.get('last_refreshed') else None
                    )
            
            return tokens
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки токенов: {str(e)}")
            return {}
    
    def _save_tokens(self):
        """Сохранить токены в файл."""
        try:
            data = {}
            for platform, accounts in self.tokens.items():
                data[platform] = {}
                for account_name, token_info in accounts.items():
                    data[platform][account_name] = {
                        'platform': token_info.platform,
                        'account_name': token_info.account_name,
                        'access_token': token_info.access_token,
                        'refresh_token': token_info.refresh_token,
                        'expires_at': token_info.expires_at.isoformat() if token_info.expires_at else None,
                        'scope': token_info.scope,
                        'created_at': token_info.created_at.isoformat() if token_info.created_at else None,
                        'last_refreshed': token_info.last_refreshed.isoformat() if token_info.last_refreshed else None
                    }
            
            with open(self.tokens_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Ошибка сохранения токенов: {str(e)}")
    
    def add_token(self, platform: str, account_name: str, access_token: str, 
                  refresh_token: Optional[str] = None, expires_in: Optional[int] = None,
                  scope: Optional[str] = None) -> bool:
        """Добавить новый токен."""
        try:
            if platform not in self.tokens:
                self.tokens[platform] = {}
            
            expires_at = None
            if expires_in:
                expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            token_info = TokenInfo(
                platform=platform,
                account_name=account_name,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=scope,
                created_at=datetime.now()
            )
            
            self.tokens[platform][account_name] = token_info
            self._save_tokens()
            
            self.logger.info(f"Добавлен токен для {platform}:{account_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления токена: {str(e)}")
            return False
    
    def get_token(self, platform: str, account_name: str) -> Optional[TokenInfo]:
        """Получить токен для конкретного аккаунта."""
        if platform in self.tokens and account_name in self.tokens[platform]:
            token_info = self.tokens[platform][account_name]
            
            # Проверить, не истек ли токен
            if self.is_token_expired(token_info):
                self.logger.warning(f"Токен истек для {platform}:{account_name}")
                if self.refresh_token_if_needed(platform, account_name):
                    return self.tokens[platform][account_name]
                else:
                    return None
            
            return token_info
        
        return None
    
    def is_token_expired(self, token_info: TokenInfo) -> bool:
        """Проверить, истек ли токен."""
        if not token_info.expires_at:
            return False  # Токен без срока истечения
        
        # Добавляем буфер в 5 минут
        buffer = timedelta(minutes=5)
        return datetime.now() + buffer >= token_info.expires_at
    
    def refresh_token_if_needed(self, platform: str, account_name: str) -> bool:
        """Обновить токен, если это необходимо."""
        token_info = self.get_token(platform, account_name)
        if not token_info:
            return False
        
        if not self.is_token_expired(token_info):
            return True  # Токен еще действителен
        
        if not token_info.refresh_token:
            self.logger.error(f"Нет refresh_token для {platform}:{account_name}")
            return False
        
        return self._refresh_token(platform, account_name, token_info)
    
    def _refresh_token(self, platform: str, account_name: str, token_info: TokenInfo) -> bool:
        """Обновить токен для конкретной платформы."""
        try:
            if platform == "instagram":
                return self._refresh_instagram_token(account_name, token_info)
            elif platform == "tiktok":
                return self._refresh_tiktok_token(account_name, token_info)
            elif platform == "youtube":
                return self._refresh_youtube_token(account_name, token_info)
            else:
                self.logger.error(f"Неподдерживаемая платформа для обновления токена: {platform}")
                return False
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления токена {platform}:{account_name}: {str(e)}")
            return False
    
    def _refresh_instagram_token(self, account_name: str, token_info: TokenInfo) -> bool:
        """Обновить токен Instagram."""
        try:
            # Instagram использует долгосрочные токены, которые можно обновить
            account_config = self._get_account_config("instagram", account_name)
            if not account_config:
                return False
            
            url = "https://graph.facebook.com/v18.0/oauth/access_token"
            params = {
                'grant_type': 'fb_exchange_token',
                'client_id': account_config.get('app_id'),
                'client_secret': account_config.get('app_secret'),
                'fb_exchange_token': token_info.access_token
            }
            
            response = requests.get(url, params=params)
            if response.ok:
                data = response.json()
                new_token = data.get('access_token')
                expires_in = data.get('expires_in', 5184000)  # 60 дней по умолчанию
                
                if new_token:
                    token_info.access_token = new_token
                    token_info.expires_at = datetime.now() + timedelta(seconds=expires_in)
                    token_info.last_refreshed = datetime.now()
                    
                    self._save_tokens()
                    self.logger.info(f"Токен Instagram обновлен для {account_name}")
                    return True
            
            self.logger.error(f"Не удалось обновить токен Instagram: {response.text}")
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления токена Instagram: {str(e)}")
            return False
    
    def _refresh_tiktok_token(self, account_name: str, token_info: TokenInfo) -> bool:
        """Обновить токен TikTok."""
        try:
            account_config = self._get_account_config("tiktok", account_name)
            if not account_config:
                return False
            
            url = "https://open-api.tiktok.com/oauth/refresh_token/"
            data = {
                'client_key': account_config.get('client_key'),
                'client_secret': account_config.get('client_secret'),
                'grant_type': 'refresh_token',
                'refresh_token': token_info.refresh_token
            }
            
            response = requests.post(url, json=data)
            if response.ok:
                result = response.json()
                if result.get('data'):
                    token_data = result['data']
                    token_info.access_token = token_data.get('access_token')
                    token_info.refresh_token = token_data.get('refresh_token')
                    token_info.expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 86400))
                    token_info.last_refreshed = datetime.now()
                    
                    self._save_tokens()
                    self.logger.info(f"Токен TikTok обновлен для {account_name}")
                    return True
            
            self.logger.error(f"Не удалось обновить токен TikTok: {response.text}")
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления токена TikTok: {str(e)}")
            return False
    
    def _refresh_youtube_token(self, account_name: str, token_info: TokenInfo) -> bool:
        """Обновить токен YouTube."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            account_config = self._get_account_config("youtube", account_name)
            if not account_config:
                return False
            
            # Создаем объект учетных данных
            creds = Credentials(
                token=token_info.access_token,
                refresh_token=token_info.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=account_config.get('client_id'),
                client_secret=account_config.get('client_secret')
            )
            
            # Обновляем токен
            creds.refresh(Request())
            
            if creds.token:
                token_info.access_token = creds.token
                if creds.expiry:
                    token_info.expires_at = creds.expiry
                token_info.last_refreshed = datetime.now()
                
                self._save_tokens()
                self.logger.info(f"Токен YouTube обновлен для {account_name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления токена YouTube: {str(e)}")
            return False
    
    def _get_account_config(self, platform: str, account_name: str) -> Optional[Dict[str, Any]]:
        """Получить конфигурацию аккаунта."""
        accounts = self.config.get('accounts', {}).get(platform, [])
        for account in accounts:
            if account.get('name') == account_name:
                return account
        return None
    
    def get_all_tokens(self, platform: Optional[str] = None) -> Dict[str, Dict[str, TokenInfo]]:
        """Получить все токены или токены для конкретной платформы."""
        if platform:
            return {platform: self.tokens.get(platform, {})}
        return self.tokens
    
    def remove_token(self, platform: str, account_name: str) -> bool:
        """Удалить токен."""
        try:
            if platform in self.tokens and account_name in self.tokens[platform]:
                del self.tokens[platform][account_name]
                if not self.tokens[platform]:  # Удалить платформу, если нет аккаунтов
                    del self.tokens[platform]
                
                self._save_tokens()
                self.logger.info(f"Токен удален для {platform}:{account_name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления токена: {str(e)}")
            return False
    
    def validate_all_tokens(self) -> Dict[str, Dict[str, bool]]:
        """Проверить все токены на валидность."""
        results = {}
        
        for platform, accounts in self.tokens.items():
            results[platform] = {}
            for account_name, token_info in accounts.items():
                is_valid = self._validate_token(token_info)
                results[platform][account_name] = is_valid
                
                if not is_valid:
                    self.logger.warning(f"Недействительный токен: {platform}:{account_name}")
        
        return results
    
    def _validate_token(self, token_info: TokenInfo) -> bool:
        """Проверить валидность токена."""
        try:
            if token_info.platform == "instagram":
                return self._validate_instagram_token(token_info)
            elif token_info.platform == "tiktok":
                return self._validate_tiktok_token(token_info)
            elif token_info.platform == "youtube":
                return self._validate_youtube_token(token_info)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка валидации токена: {str(e)}")
            return False
    
    def _validate_instagram_token(self, token_info: TokenInfo) -> bool:
        """Проверить токен Instagram."""
        try:
            url = "https://graph.facebook.com/v18.0/me"
            params = {'access_token': token_info.access_token}
            
            response = requests.get(url, params=params)
            return response.ok
            
        except Exception:
            return False
    
    def _validate_tiktok_token(self, token_info: TokenInfo) -> bool:
        """Проверить токен TikTok."""
        try:
            url = "https://open-api.tiktok.com/user/info/"
            params = {'access_token': token_info.access_token}
            
            response = requests.get(url, params=params)
            return response.ok
            
        except Exception:
            return False
    
    def _validate_youtube_token(self, token_info: TokenInfo) -> bool:
        """Проверить токен YouTube."""
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            
            account_config = self._get_account_config("youtube", token_info.account_name)
            if not account_config:
                return False
            
            creds = Credentials(
                token=token_info.access_token,
                refresh_token=token_info.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=account_config.get('client_id'),
                client_secret=account_config.get('client_secret')
            )
            
            service = build('youtube', 'v3', credentials=creds)
            response = service.channels().list(part='snippet', mine=True).execute()
            
            return bool(response.get('items'))
            
        except Exception:
            return False
    
    def get_token_status(self) -> Dict[str, Any]:
        """Получить статус всех токенов."""
        status = {
            'total_tokens': 0,
            'valid_tokens': 0,
            'expired_tokens': 0,
            'platforms': {}
        }
        
        for platform, accounts in self.tokens.items():
            platform_status = {
                'total': len(accounts),
                'valid': 0,
                'expired': 0,
                'accounts': {}
            }
            
            for account_name, token_info in accounts.items():
                is_expired = self.is_token_expired(token_info)
                is_valid = self._validate_token(token_info) if not is_expired else False
                
                platform_status['accounts'][account_name] = {
                    'valid': is_valid,
                    'expired': is_expired,
                    'expires_at': token_info.expires_at.isoformat() if token_info.expires_at else None,
                    'last_refreshed': token_info.last_refreshed.isoformat() if token_info.last_refreshed else None
                }
                
                if is_valid:
                    platform_status['valid'] += 1
                if is_expired:
                    platform_status['expired'] += 1
            
            status['platforms'][platform] = platform_status
            status['total_tokens'] += platform_status['total']
            status['valid_tokens'] += platform_status['valid']
            status['expired_tokens'] += platform_status['expired']
        
        return status
