#!/usr/bin/env python3
"""
Утилита для безопасной настройки множественных аккаунтов с использованием переменных окружения.
"""

import os
import sys
import shutil
from pathlib import Path

# Добавить путь к модулям
sys.path.append(str(Path(__file__).parent / "src"))

from src.config_loader import ConfigLoader
from src.logger import get_logger


def main():
    """Главная функция настройки."""
    
    print("🔒 БЕЗОПАСНАЯ НАСТРОЙКА МНОЖЕСТВЕННЫХ АККАУНТОВ")
    print("=" * 55)
    
    logger = get_logger("secure_setup")
    
    # Проверить текущее состояние
    print("\n1. 🔍 Проверка текущей конфигурации...")
    
    config_loader = ConfigLoader()
    status = config_loader.check_env_completeness()
    
    if 'error' in status:
        print(f"   ❌ Ошибка конфигурации: {status['error']}")
        return
    
    print(f"   📊 Всего аккаунтов в конфиге: {status['total_accounts']}")
    print(f"   ✅ Включенных аккаунтов: {status['enabled_accounts']}")
    print(f"   🔧 Настроенных аккаунтов: {status['configured_accounts']}")
    print(f"   📁 Файл .env существует: {status['env_file_exists']}")
    print(f"   🚀 Готов к использованию: {status['ready_for_use']}")
    
    if status['missing_env_vars']:
        print(f"   ⚠️  Недостающие переменные окружения: {len(status['missing_env_vars'])}")
        for var in sorted(status['missing_env_vars']):
            print(f"      - {var}")
    
    # Если уже настроено
    if status['ready_for_use']:
        print("\n🎉 Система уже настроена и готова к использованию!")
        
        choice = input("\n👉 Хотите пересоздать настройки? (y/n): ").strip().lower()
        if choice != 'y':
            print("👋 Настройка завершена")
            return
    
    # Создание .env файла
    print("\n2. 📝 Настройка файла переменных окружения...")
    
    env_file = Path(".env")
    env_template = Path("env_template.txt")
    
    if not env_file.exists():
        if env_template.exists():
            print(f"   📋 Копирование {env_template} в {env_file}...")
            shutil.copy(env_template, env_file)
            print(f"   ✅ Файл {env_file} создан")
        else:
            print(f"   ❌ Файл {env_template} не найден")
            create_choice = input("   👉 Создать базовый .env файл? (y/n): ").strip().lower()
            
            if create_choice == 'y':
                create_basic_env_file()
            else:
                print("   ⚠️  Без .env файла настройка невозможна")
                return
    else:
        print(f"   ✅ Файл {env_file} уже существует")
    
    # Интерактивная настройка переменных
    print("\n3. 🔧 Интерактивная настройка переменных...")
    
    if not interactive_env_setup():
        print("   ❌ Настройка прервана")
        return
    
    # Проверка после настройки
    print("\n4. ✅ Проверка настройки...")
    
    new_status = config_loader.check_env_completeness()
    
    if new_status['ready_for_use']:
        print("   🎉 Настройка завершена успешно!")
        
        # Включить аккаунты
        enable_choice = input("\n👉 Включить настроенные аккаунты? (y/n): ").strip().lower()
        if enable_choice == 'y':
            enable_accounts()
        
        # Следующие шаги
        show_next_steps()
        
    else:
        print("   ⚠️  Настройка не завершена")
        if new_status['missing_env_vars']:
            print("   Недостающие переменные:")
            for var in sorted(new_status['missing_env_vars']):
                print(f"      - {var}")


def create_basic_env_file():
    """Создать базовый .env файл."""
    
    basic_content = """# Instagram API Configuration
INSTAGRAM_MAIN_APP_ID=your_instagram_app_id_here
INSTAGRAM_MAIN_APP_SECRET=your_instagram_app_secret_here

# TikTok API Configuration  
TIKTOK_MAIN_CLIENT_KEY=your_tiktok_client_key_here
TIKTOK_MAIN_CLIENT_SECRET=your_tiktok_client_secret_here

# YouTube API Configuration
YOUTUBE_MAIN_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_MAIN_CLIENT_SECRET=your_youtube_client_secret_here

# Notification Configuration (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
"""
    
    try:
        with open(".env", "w") as f:
            f.write(basic_content)
        print("   ✅ Базовый .env файл создан")
        return True
    except Exception as e:
        print(f"   ❌ Ошибка создания .env файла: {e}")
        return False


def interactive_env_setup():
    """Интерактивная настройка переменных окружения."""
    
    print("\n   📋 Настройка API ключей для каждой платформы...")
    print("   💡 Нажмите Enter чтобы пропустить переменную")
    
    # Загрузить текущий .env
    env_vars = load_env_file()
    
    # Группы переменных
    var_groups = {
        "Instagram": [
            ("INSTAGRAM_MAIN_APP_ID", "Instagram App ID (основной аккаунт)"),
            ("INSTAGRAM_MAIN_APP_SECRET", "Instagram App Secret (основной аккаунт)"),
            ("INSTAGRAM_BACKUP_APP_ID", "Instagram App ID (резервный аккаунт)"),
            ("INSTAGRAM_BACKUP_APP_SECRET", "Instagram App Secret (резервный аккаунт)"),
        ],
        "TikTok": [
            ("TIKTOK_MAIN_CLIENT_KEY", "TikTok Client Key (основной аккаунт)"),
            ("TIKTOK_MAIN_CLIENT_SECRET", "TikTok Client Secret (основной аккаунт)"),
            ("TIKTOK_BACKUP_CLIENT_KEY", "TikTok Client Key (резервный аккаунт)"),
            ("TIKTOK_BACKUP_CLIENT_SECRET", "TikTok Client Secret (резервный аккаунт)"),
        ],
        "YouTube": [
            ("YOUTUBE_MAIN_CLIENT_ID", "YouTube Client ID (основной канал)"),
            ("YOUTUBE_MAIN_CLIENT_SECRET", "YouTube Client Secret (основной канал)"),
            ("YOUTUBE_BACKUP_CLIENT_ID", "YouTube Client ID (резервный канал)"),
            ("YOUTUBE_BACKUP_CLIENT_SECRET", "YouTube Client Secret (резервный канал)"),
        ]
    }
    
    updated_vars = {}
    
    for group_name, variables in var_groups.items():
        print(f"\n   📱 {group_name}:")
        
        setup_group = input(f"      👉 Настроить {group_name}? (y/n): ").strip().lower()
        if setup_group != 'y':
            print(f"      ⏭️  Пропуск {group_name}")
            continue
        
        for var_name, var_description in variables:
            current_value = env_vars.get(var_name, "")
            
            if current_value and not current_value.startswith("your_"):
                print(f"      ✅ {var_name}: уже настроено")
                continue
            
            print(f"\n      🔑 {var_description}")
            if current_value:
                print(f"         Текущее значение: {current_value}")
            
            new_value = input(f"      👉 Введите значение: ").strip()
            
            if new_value:
                updated_vars[var_name] = new_value
                print(f"      ✅ {var_name} обновлено")
            else:
                print(f"      ⏭️  {var_name} пропущено")
    
    # Сохранить обновленные переменные
    if updated_vars:
        print(f"\n   💾 Сохранение {len(updated_vars)} переменных...")
        
        # Обновить env_vars
        env_vars.update(updated_vars)
        
        # Записать обратно в файл
        if save_env_file(env_vars):
            print("   ✅ Переменные сохранены в .env")
            return True
        else:
            print("   ❌ Ошибка сохранения переменных")
            return False
    else:
        print("   ⚠️  Переменные не изменены")
        return True


def load_env_file():
    """Загрузить переменные из .env файла."""
    env_vars = {}
    
    try:
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    
    return env_vars


def save_env_file(env_vars):
    """Сохранить переменные в .env файл."""
    try:
        lines = []
        
        # Группировать переменные
        groups = {
            "# Instagram API Configuration": [k for k in env_vars.keys() if "INSTAGRAM" in k],
            "# TikTok API Configuration": [k for k in env_vars.keys() if "TIKTOK" in k],
            "# YouTube API Configuration": [k for k in env_vars.keys() if "YOUTUBE" in k],
            "# Other Configuration": [k for k in env_vars.keys() if not any(p in k for p in ["INSTAGRAM", "TIKTOK", "YOUTUBE"])]
        }
        
        for group_header, group_vars in groups.items():
            if group_vars:
                lines.append(group_header)
                for var in sorted(group_vars):
                    lines.append(f"{var}={env_vars[var]}")
                lines.append("")
        
        with open(".env", "w") as f:
            f.write("\n".join(lines))
        
        return True
        
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return False


def enable_accounts():
    """Включить настроенные аккаунты в config.yaml."""
    print("\n   🔧 Включение настроенных аккаунтов...")
    
    try:
        # Читать config.yaml
        with open("config.yaml", "r") as f:
            content = f.read()
        
        # Заменить enabled: false на enabled: true для настроенных аккаунтов
        # Простая замена - в реальной системе лучше использовать YAML парсер
        updated_content = content.replace("enabled: false  # включите после настройки .env", "enabled: true")
        
        # Записать обратно
        with open("config.yaml", "w") as f:
            f.write(updated_content)
        
        print("   ✅ Аккаунты включены в config.yaml")
        
    except Exception as e:
        print(f"   ❌ Ошибка включения аккаунтов: {e}")


def show_next_steps():
    """Показать следующие шаги."""
    
    print("\n" + "=" * 55)
    print("🚀 СЛЕДУЮЩИЕ ШАГИ")
    print("=" * 55)
    
    print("\n1. 🔐 Авторизуйте аккаунты:")
    print("   python account_manager.py authorize --all")
    
    print("\n2. ✅ Проверьте статус:")
    print("   python account_manager.py status")
    
    print("\n3. 📤 Протестируйте публикацию:")
    print("   python main.py post 'path/to/video.mp4' --caption 'Test post'")
    
    print("\n4. 🎮 Используйте интерактивный интерфейс:")
    print("   python example_multiple_accounts.py")
    
    print("\n🔒 БЕЗОПАСНОСТЬ:")
    print("   - Файл .env НЕ должен попадать в git")
    print("   - Регулярно обновляйте API ключи")
    print("   - Используйте разные приложения для разных аккаунтов")


if __name__ == "__main__":
    main()
