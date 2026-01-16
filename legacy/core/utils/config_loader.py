"""
Безопасная загрузка конфигурации с поддержкой переменных окружения.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from core.utils.logger import get_logger


class ConfigLoader:
    """Загрузчик конфигурации с поддержкой переменных окружения."""
    
    def __init__(self, config_path: str = "config.yaml", env_file: str = ".env"):
        self.config_path = config_path
        self.env_file = env_file
        self.logger = get_logger("config_loader")
        
        # Загрузить переменные окружения
        self._load_environment()
    
    def _load_environment(self):
        """Загрузить переменные окружения из файла."""
        env_path = Path(self.env_file)
        
        if env_path.exists():
            load_dotenv(env_path)
            self.logger.info(f"Загружены переменные окружения из {self.env_file}")
        else:
            self.logger.warning(f"Файл переменных окружения не найден: {self.env_file}")
            
            # Проверить, есть ли пример файла
            example_path = Path(f"{self.env_file}.example")
            if not example_path.exists():
                example_path = Path("env.example")
            
            if example_path.exists():
                self.logger.info(f"Найден пример файла: {example_path}")
                self.logger.info(f"Скопируйте его в {self.env_file} и заполните реальными данными")
    
    def load_config(self) -> Dict[str, Any]:
        """Загрузить конфигурацию с подстановкой переменных окружения."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_content = file.read()
            
            # Заменить переменные окружения
            resolved_content = self._resolve_env_variables(config_content)
            
            # Парсить YAML
            config = yaml.safe_load(resolved_content)
            
            # Валидировать конфигурацию
            self._validate_config(config)
            
            self.logger.info(f"Конфигурация успешно загружена из {self.config_path}")
            return config
            
        except FileNotFoundError:
            self.logger.error(f"Файл конфигурации не найден: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            self.logger.error(f"Ошибка парсинга YAML: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации: {e}")
            raise
    
    def _resolve_env_variables(self, content: str) -> str:
        """Заменить переменные окружения в формате ${VAR_NAME}."""
        def replace_var(match):
            var_name = match.group(1)
            var_value = os.getenv(var_name)
            
            if var_value is None:
                self.logger.warning(f"Переменная окружения не найдена: {var_name}")
                return f"MISSING_{var_name}"
            
            return var_value
        
        # Паттерн для поиска ${VAR_NAME}
        pattern = r'\$\{([^}]+)\}'
        resolved_content = re.sub(pattern, replace_var, content)
        
        return resolved_content
    
    def _validate_config(self, config: Dict[str, Any]):
        """Валидировать загруженную конфигурацию."""
        if not config:
            raise ValueError("Конфигурация пуста")
        
        # Проверить наличие основных разделов
        required_sections = ['accounts', 'platforms']
        for section in required_sections:
            if section not in config:
                self.logger.warning(f"Отсутствует раздел конфигурации: {section}")
        
        # Проверить аккаунты на наличие недостающих переменных
        accounts = config.get('accounts', {})
        missing_vars = set()
        
        for platform, platform_accounts in accounts.items():
            if not isinstance(platform_accounts, list):
                continue
                
            for account in platform_accounts:
                if not isinstance(account, dict):
                    continue
                
                # Проверить обязательные поля на наличие MISSING_
                for key, value in account.items():
                    if isinstance(value, str) and value.startswith('MISSING_'):
                        var_name = value.replace('MISSING_', '')
                        missing_vars.add(var_name)
        
        if missing_vars:
            self.logger.error("Не найдены переменные окружения:")
            for var in sorted(missing_vars):
                self.logger.error(f"  - {var}")
            
            self.logger.info("Создайте файл .env и добавьте недостающие переменные:")
            for var in sorted(missing_vars):
                self.logger.info(f"  {var}=your_value_here")
    
    def get_missing_env_vars(self, config: Dict[str, Any]) -> set:
        """Получить список недостающих переменных окружения."""
        missing_vars = set()
        
        def check_dict(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    check_dict(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_dict(item, f"{path}[{i}]")
            elif isinstance(obj, str) and obj.startswith('MISSING_'):
                var_name = obj.replace('MISSING_', '')
                missing_vars.add(var_name)
        
        check_dict(config)
        return missing_vars
    
    def create_env_template(self, config: Dict[str, Any], output_path: str = ".env.template"):
        """Создать шаблон файла переменных окружения на основе конфигурации."""
        try:
            env_vars = set()
            
            # Найти все переменные в конфигурации
            def find_vars(obj):
                if isinstance(obj, dict):
                    for value in obj.values():
                        find_vars(value)
                elif isinstance(obj, list):
                    for item in obj:
                        find_vars(item)
                elif isinstance(obj, str):
                    # Найти ${VAR_NAME}
                    import re
                    matches = re.findall(r'\$\{([^}]+)\}', obj)
                    env_vars.update(matches)
            
            find_vars(config)
            
            # Создать шаблон
            template_lines = [
                "# Переменные окружения для Content Fabric",
                "# Скопируйте этот файл в .env и заполните реальными значениями",
                "",
                "# Instagram API Configuration"
            ]
            
            instagram_vars = [var for var in env_vars if 'INSTAGRAM' in var]
            for var in sorted(instagram_vars):
                template_lines.append(f"{var}=your_value_here")
            
            template_lines.extend([
                "",
                "# TikTok API Configuration"
            ])
            
            tiktok_vars = [var for var in env_vars if 'TIKTOK' in var]
            for var in sorted(tiktok_vars):
                template_lines.append(f"{var}=your_value_here")
            
            template_lines.extend([
                "",
                "# YouTube API Configuration"
            ])
            
            youtube_vars = [var for var in env_vars if 'YOUTUBE' in var]
            for var in sorted(youtube_vars):
                template_lines.append(f"{var}=your_value_here")
            
            # Остальные переменные
            other_vars = [var for var in env_vars if not any(platform in var for platform in ['INSTAGRAM', 'TIKTOK', 'YOUTUBE'])]
            if other_vars:
                template_lines.extend([
                    "",
                    "# Other Configuration"
                ])
                for var in sorted(other_vars):
                    template_lines.append(f"{var}=your_value_here")
            
            # Записать файл
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(template_lines))
            
            self.logger.info(f"Создан шаблон переменных окружения: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка создания шаблона: {e}")
            return False
    
    def check_env_completeness(self) -> Dict[str, Any]:
        """Проверить полноту настройки переменных окружения."""
        try:
            config = self.load_config()
            missing_vars = self.get_missing_env_vars(config)
            
            accounts = config.get('accounts', {})
            total_accounts = 0
            enabled_accounts = 0
            configured_accounts = 0
            
            for platform, platform_accounts in accounts.items():
                if not isinstance(platform_accounts, list):
                    continue
                
                for account in platform_accounts:
                    if not isinstance(account, dict):
                        continue
                    
                    total_accounts += 1
                    
                    if account.get('enabled', False):
                        enabled_accounts += 1
                    
                    # Проверить, настроен ли аккаунт (нет MISSING_ значений)
                    has_missing = False
                    for value in account.values():
                        if isinstance(value, str) and value.startswith('MISSING_'):
                            has_missing = True
                            break
                    
                    if not has_missing:
                        configured_accounts += 1
            
            return {
                'total_accounts': total_accounts,
                'enabled_accounts': enabled_accounts,
                'configured_accounts': configured_accounts,
                'missing_env_vars': missing_vars,
                'env_file_exists': Path(self.env_file).exists(),
                'ready_for_use': len(missing_vars) == 0 and enabled_accounts > 0
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки конфигурации: {e}")
            return {
                'error': str(e),
                'ready_for_use': False
            }


def load_secure_config(config_path: str = "config.yaml", env_file: str = ".env") -> Dict[str, Any]:
    """Удобная функция для загрузки безопасной конфигурации."""
    loader = ConfigLoader(config_path, env_file)
    return loader.load_config()
