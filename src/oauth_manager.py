"""
Система автоматизированного получения токенов OAuth для всех социальных платформ.
"""

import os
import json
import time
import webbrowser
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from urllib.parse import urlparse, parse_qs
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import yaml

from .logger import get_logger
from .token_manager import TokenManager


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Обработчик OAuth callback'ов."""
    
    def __init__(self, callback_func: Callable, *args, **kwargs):
        self.callback_func = callback_func
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Обработать GET запрос с OAuth кодом."""
        try:
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Получить код авторизации
            code = query_params.get('code', [None])[0]
            error = query_params.get('error', [None])[0]
            state = query_params.get('state', [None])[0]
            
            if error:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f'<html><body><h1>Ошибка авторизации: {error}</h1></body></html>'.encode())
                self.callback_func(None, error, state)
            elif code:
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write('<html><body><h1>Авторизация успешна!</h1><p>Можете закрыть это окно.</p></body></html>'.encode())
                self.callback_func(code, None, state)
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write('<html><body><h1>Неверные параметры авторизации</h1></body></html>'.encode())
                self.callback_func(None, "Неверные параметры", state)
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f'<html><body><h1>Внутренняя ошибка: {str(e)}</h1></body></html>'.encode())
            self.callback_func(None, str(e), None)
    
    def log_message(self, format, *args):
        """Отключить логирование HTTP сервера."""
        pass


class OAuthManager:
    """Менеджер для автоматизированного получения OAuth токенов."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = get_logger("oauth_manager")
        self.token_manager = TokenManager(config_path)
        self.callback_port = 8080
        self.callback_server = None
        self.auth_result = None
        
    def _load_config(self) -> dict:
        """Загрузить конфигурацию из YAML файла."""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            self.logger.error(f"Файл конфигурации не найден: {self.config_path}")
            return {}
    
    def get_authorization_url(self, platform: str, account_name: str, 
                            custom_scopes: Optional[list] = None) -> Optional[str]:
        """Получить URL для авторизации на платформе."""
        try:
            if platform == "instagram":
                return self._get_instagram_auth_url(account_name, custom_scopes)
            elif platform == "tiktok":
                return self._get_tiktok_auth_url(account_name, custom_scopes)
            elif platform == "youtube":
                return self._get_youtube_auth_url(account_name, custom_scopes)
            else:
                self.logger.error(f"Неподдерживаемая платформа: {platform}")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка получения URL авторизации: {str(e)}")
            return None
    
    def _get_instagram_auth_url(self, account_name: str, custom_scopes: Optional[list] = None) -> Optional[str]:
        """Получить URL авторизации Instagram."""
        account_config = self._get_account_config("instagram", account_name)
        if not account_config:
            return None
        
        app_id = account_config.get('app_id')
        if not app_id:
            self.logger.error(f"Не найден app_id для Instagram аккаунта {account_name}")
            return None
        
        scopes = custom_scopes or [
            'instagram_basic',
            'instagram_content_publish',
            'pages_show_list',
            'pages_read_engagement'
        ]
        
        redirect_uri = f"http://localhost:{self.callback_port}/callback"
        state = f"instagram_{account_name}_{int(time.time())}"
        
        params = {
            'client_id': app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(scopes),
            'response_type': 'code',
            'state': state
        }
        
        base_url = "https://api.instagram.com/oauth/authorize"
        auth_url = base_url + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        self.logger.info(f"Создан URL авторизации Instagram для {account_name}")
        return auth_url
    
    def _get_tiktok_auth_url(self, account_name: str, custom_scopes: Optional[list] = None) -> Optional[str]:
        """Получить URL авторизации TikTok."""
        account_config = self._get_account_config("tiktok", account_name)
        if not account_config:
            return None
        
        client_key = account_config.get('client_key')
        if not client_key:
            self.logger.error(f"Не найден client_key для TikTok аккаунта {account_name}")
            return None
        
        scopes = custom_scopes or [
            'user.info.basic',
            'video.upload',
            'video.publish'
        ]
        
        redirect_uri = f"http://localhost:{self.callback_port}/callback"
        state = f"tiktok_{account_name}_{int(time.time())}"
        
        params = {
            'client_key': client_key,
            'redirect_uri': redirect_uri,
            'scope': ','.join(scopes),
            'response_type': 'code',
            'state': state
        }
        
        base_url = "https://www.tiktok.com/auth/authorize/"
        auth_url = base_url + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        self.logger.info(f"Создан URL авторизации TikTok для {account_name}")
        return auth_url
    
    def _get_youtube_auth_url(self, account_name: str, custom_scopes: Optional[list] = None) -> Optional[str]:
        """Получить URL авторизации YouTube."""
        account_config = self._get_account_config("youtube", account_name)
        if not account_config:
            return None
        
        client_id = account_config.get('client_id')
        if not client_id:
            self.logger.error(f"Не найден client_id для YouTube аккаунта {account_name}")
            return None
        
        scopes = custom_scopes or [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]
        
        redirect_uri = f"http://localhost:{self.callback_port}/callback"
        state = f"youtube_{account_name}_{int(time.time())}"
        
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(scopes),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state
        }
        
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        auth_url = base_url + "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        self.logger.info(f"Создан URL авторизации YouTube для {account_name}")
        return auth_url
    
    def authorize_account(self, platform: str, account_name: str, 
                         custom_scopes: Optional[list] = None, 
                         auto_open_browser: bool = True) -> Dict[str, Any]:
        """Автоматически авторизовать аккаунт."""
        try:
            # Получить URL авторизации
            auth_url = self.get_authorization_url(platform, account_name, custom_scopes)
            if not auth_url:
                return {
                    'success': False,
                    'error': 'Не удалось создать URL авторизации'
                }
            
            # Запустить локальный сервер для callback'а
            self.auth_result = None
            callback_handler = lambda *args: OAuthCallbackHandler(self._oauth_callback, *args)
            
            try:
                self.callback_server = HTTPServer(('localhost', self.callback_port), callback_handler)
                server_thread = threading.Thread(target=self.callback_server.serve_forever)
                server_thread.daemon = True
                server_thread.start()
                
                self.logger.info(f"Запущен callback сервер на порту {self.callback_port}")
                
                # Открыть браузер для авторизации
                if auto_open_browser:
                    webbrowser.open(auth_url)
                    self.logger.info("Браузер открыт для авторизации")
                else:
                    self.logger.info(f"Перейдите по ссылке для авторизации: {auth_url}")
                
                # Ожидать результат авторизации
                timeout = 300  # 5 минут
                start_time = time.time()
                
                while self.auth_result is None and (time.time() - start_time) < timeout:
                    time.sleep(1)
                
                # Остановить сервер
                self.callback_server.shutdown()
                self.callback_server = None
                
                if self.auth_result is None:
                    return {
                        'success': False,
                        'error': 'Превышено время ожидания авторизации'
                    }
                
                if self.auth_result.get('error'):
                    return {
                        'success': False,
                        'error': self.auth_result['error']
                    }
                
                # Обменять код на токен
                code = self.auth_result.get('code')
                state = self.auth_result.get('state')
                
                if not code:
                    return {
                        'success': False,
                        'error': 'Не получен код авторизации'
                    }
                
                # Получить токен доступа
                token_result = self._exchange_code_for_token(platform, account_name, code, state)
                
                if token_result.get('success'):
                    self.logger.info(f"Успешно авторизован аккаунт {platform}:{account_name}")
                
                return token_result
                
            except Exception as e:
                if self.callback_server:
                    self.callback_server.shutdown()
                    self.callback_server = None
                raise e
                
        except Exception as e:
            self.logger.error(f"Ошибка авторизации аккаунта: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _oauth_callback(self, code: Optional[str], error: Optional[str], state: Optional[str]):
        """Callback функция для обработки результата OAuth."""
        self.auth_result = {
            'code': code,
            'error': error,
            'state': state
        }
    
    def _exchange_code_for_token(self, platform: str, account_name: str, 
                               code: str, state: Optional[str]) -> Dict[str, Any]:
        """Обменять код авторизации на токен доступа."""
        try:
            if platform == "instagram":
                return self._exchange_instagram_code(account_name, code)
            elif platform == "tiktok":
                return self._exchange_tiktok_code(account_name, code)
            elif platform == "youtube":
                return self._exchange_youtube_code(account_name, code)
            else:
                return {
                    'success': False,
                    'error': f'Неподдерживаемая платформа: {platform}'
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка обмена кода на токен: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _exchange_instagram_code(self, account_name: str, code: str) -> Dict[str, Any]:
        """Обменять код Instagram на токен."""
        account_config = self._get_account_config("instagram", account_name)
        if not account_config:
            return {'success': False, 'error': 'Конфигурация аккаунта не найдена'}
        
        # Шаг 1: Получить краткосрочный токен
        url = "https://api.instagram.com/oauth/access_token"
        data = {
            'client_id': account_config.get('app_id'),
            'client_secret': account_config.get('app_secret'),
            'grant_type': 'authorization_code',
            'redirect_uri': f"http://localhost:{self.callback_port}/callback",
            'code': code
        }
        
        response = requests.post(url, data=data)
        if not response.ok:
            return {
                'success': False,
                'error': f'Ошибка получения токена: {response.text}'
            }
        
        token_data = response.json()
        short_token = token_data.get('access_token')
        
        if not short_token:
            return {
                'success': False,
                'error': 'Не получен краткосрочный токен'
            }
        
        # Шаг 2: Обменять на долгосрочный токен
        long_token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        long_token_params = {
            'grant_type': 'ig_exchange_token',
            'client_secret': account_config.get('app_secret'),
            'access_token': short_token
        }
        
        long_response = requests.get(long_token_url, params=long_token_params)
        if not long_response.ok:
            return {
                'success': False,
                'error': f'Ошибка получения долгосрочного токена: {long_response.text}'
            }
        
        long_token_data = long_response.json()
        access_token = long_token_data.get('access_token')
        expires_in = long_token_data.get('expires_in', 5184000)  # 60 дней
        
        # Сохранить токен
        success = self.token_manager.add_token(
            platform="instagram",
            account_name=account_name,
            access_token=access_token,
            expires_in=expires_in
        )
        
        if success:
            return {
                'success': True,
                'access_token': access_token,
                'expires_in': expires_in
            }
        else:
            return {
                'success': False,
                'error': 'Не удалось сохранить токен'
            }
    
    def _exchange_tiktok_code(self, account_name: str, code: str) -> Dict[str, Any]:
        """Обменять код TikTok на токен."""
        account_config = self._get_account_config("tiktok", account_name)
        if not account_config:
            return {'success': False, 'error': 'Конфигурация аккаунта не найдена'}
        
        url = "https://open-api.tiktok.com/oauth/access_token/"
        data = {
            'client_key': account_config.get('client_key'),
            'client_secret': account_config.get('client_secret'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': f"http://localhost:{self.callback_port}/callback"
        }
        
        response = requests.post(url, json=data)
        if not response.ok:
            return {
                'success': False,
                'error': f'Ошибка получения токена: {response.text}'
            }
        
        result = response.json()
        if not result.get('data'):
            return {
                'success': False,
                'error': f'Неверный ответ API: {result}'
            }
        
        token_data = result['data']
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 86400)  # 24 часа
        scope = token_data.get('scope')
        
        # Сохранить токен
        success = self.token_manager.add_token(
            platform="tiktok",
            account_name=account_name,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            scope=scope
        )
        
        if success:
            return {
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': expires_in,
                'scope': scope
            }
        else:
            return {
                'success': False,
                'error': 'Не удалось сохранить токен'
            }
    
    def _exchange_youtube_code(self, account_name: str, code: str) -> Dict[str, Any]:
        """Обменять код YouTube на токен."""
        account_config = self._get_account_config("youtube", account_name)
        if not account_config:
            return {'success': False, 'error': 'Конфигурация аккаунта не найдена'}
        
        url = "https://oauth2.googleapis.com/token"
        data = {
            'client_id': account_config.get('client_id'),
            'client_secret': account_config.get('client_secret'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': f"http://localhost:{self.callback_port}/callback"
        }
        
        response = requests.post(url, data=data)
        if not response.ok:
            return {
                'success': False,
                'error': f'Ошибка получения токена: {response.text}'
            }
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 3600)  # 1 час
        scope = token_data.get('scope')
        
        # Сохранить токен
        success = self.token_manager.add_token(
            platform="youtube",
            account_name=account_name,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            scope=scope
        )
        
        if success:
            return {
                'success': True,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': expires_in,
                'scope': scope
            }
        else:
            return {
                'success': False,
                'error': 'Не удалось сохранить токен'
            }
    
    def _get_account_config(self, platform: str, account_name: str) -> Optional[Dict[str, Any]]:
        """Получить конфигурацию аккаунта."""
        accounts = self.config.get('accounts', {}).get(platform, [])
        for account in accounts:
            if account.get('name') == account_name:
                return account
        return None
    
    def authorize_all_accounts(self, platform: Optional[str] = None) -> Dict[str, Any]:
        """Авторизовать все аккаунты для платформы или всех платформ."""
        results = {}
        
        platforms = [platform] if platform else ['instagram', 'tiktok', 'youtube']
        
        for plat in platforms:
            results[plat] = {}
            accounts = self.config.get('accounts', {}).get(plat, [])
            
            for account in accounts:
                account_name = account.get('name')
                if not account_name:
                    continue
                
                self.logger.info(f"Авторизация {plat}:{account_name}")
                result = self.authorize_account(plat, account_name)
                results[plat][account_name] = result
                
                if result.get('success'):
                    self.logger.info(f"✅ Успешно авторизован {plat}:{account_name}")
                else:
                    self.logger.error(f"❌ Ошибка авторизации {plat}:{account_name}: {result.get('error')}")
                
                # Небольшая пауза между авторизациями
                time.sleep(2)
        
        return results
    
    def get_account_status(self) -> Dict[str, Any]:
        """Получить статус авторизации всех аккаунтов."""
        status = {
            'total_accounts': 0,
            'authorized_accounts': 0,
            'platforms': {}
        }
        
        token_status = self.token_manager.get_token_status()
        
        for platform in ['instagram', 'tiktok', 'youtube']:
            accounts = self.config.get('accounts', {}).get(platform, [])
            platform_status = {
                'total': len(accounts),
                'authorized': 0,
                'accounts': {}
            }
            
            for account in accounts:
                account_name = account.get('name')
                if not account_name:
                    continue
                
                # Проверить наличие токена
                token_info = self.token_manager.get_token(platform, account_name)
                is_authorized = token_info is not None
                
                platform_status['accounts'][account_name] = {
                    'authorized': is_authorized,
                    'token_valid': False,
                    'expires_at': None
                }
                
                if is_authorized:
                    platform_status['authorized'] += 1
                    
                    # Дополнительная информация из token_status
                    platform_tokens = token_status.get('platforms', {}).get(platform, {})
                    account_token_info = platform_tokens.get('accounts', {}).get(account_name, {})
                    
                    platform_status['accounts'][account_name].update({
                        'token_valid': account_token_info.get('valid', False),
                        'expires_at': account_token_info.get('expires_at'),
                        'last_refreshed': account_token_info.get('last_refreshed')
                    })
            
            status['platforms'][platform] = platform_status
            status['total_accounts'] += platform_status['total']
            status['authorized_accounts'] += platform_status['authorized']
        
        return status
