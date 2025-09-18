#!/usr/bin/env python3
"""
Пример использования системы с множественными аккаунтами.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# Добавить путь к модулям
sys.path.append(str(Path(__file__).parent / "src"))

from src.auto_poster import SocialMediaAutoPoster


def main():
    """Основная функция с примерами использования."""
    
    print("🚀 Инициализация системы автопостинга...")
    
    try:
        # Инициализировать автопостер
        auto_poster = SocialMediaAutoPoster()
        print("✅ Система инициализирована успешно")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        return
    
    # Примеры использования
    while True:
        print("\n" + "="*60)
        print("📱 СИСТЕМА УПРАВЛЕНИЯ МНОЖЕСТВЕННЫМИ АККАУНТАМИ")
        print("="*60)
        print("1. 📊 Проверить статус всех аккаунтов")
        print("2. 🔐 Авторизовать аккаунты")
        print("3. 🔄 Обновить токены")
        print("4. ✅ Валидировать аккаунты")
        print("5. 📤 Опубликовать контент немедленно")
        print("6. ⏰ Запланировать публикацию")
        print("7. 📋 Показать запланированные посты")
        print("8. 🛠️ Управление токенами")
        print("9. 🔍 Подробная информация о системе")
        print("0. ❌ Выход")
        
        choice = input("\n👉 Выберите действие (0-9): ").strip()
        
        if choice == "0":
            print("👋 До свидания!")
            break
        elif choice == "1":
            check_accounts_status(auto_poster)
        elif choice == "2":
            authorize_accounts(auto_poster)
        elif choice == "3":
            refresh_tokens(auto_poster)
        elif choice == "4":
            validate_accounts(auto_poster)
        elif choice == "5":
            post_immediately(auto_poster)
        elif choice == "6":
            schedule_post(auto_poster)
        elif choice == "7":
            show_scheduled_posts(auto_poster)
        elif choice == "8":
            manage_tokens(auto_poster)
        elif choice == "9":
            show_system_info(auto_poster)
        else:
            print("❌ Неверный выбор. Попробуйте еще раз.")
        
        input("\n⏸️ Нажмите Enter для продолжения...")


def check_accounts_status(auto_poster: SocialMediaAutoPoster):
    """Проверить статус всех аккаунтов."""
    print("\n🔍 Проверка статуса аккаунтов...")
    
    try:
        system_status = auto_poster.get_system_status()
        account_status = system_status.get('account_status', {})
        token_status = system_status.get('token_status', {})
        
        print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего аккаунтов: {account_status.get('total_accounts', 0)}")
        print(f"   Авторизованных: {account_status.get('authorized_accounts', 0)}")
        print(f"   Всего токенов: {token_status.get('total_tokens', 0)}")
        print(f"   Действительных токенов: {token_status.get('valid_tokens', 0)}")
        print(f"   Истекших токенов: {token_status.get('expired_tokens', 0)}")
        
        for platform in ['instagram', 'tiktok', 'youtube']:
            platform_accounts = account_status.get('platforms', {}).get(platform, {})
            platform_tokens = token_status.get('platforms', {}).get(platform, {})
            
            print(f"\n📱 {platform.upper()}:")
            print(f"   Всего аккаунтов: {platform_accounts.get('total', 0)}")
            print(f"   Авторизованных: {platform_accounts.get('authorized', 0)}")
            
            if platform_tokens:
                print(f"   Действительных токенов: {platform_tokens.get('valid', 0)}")
                print(f"   Истекших токенов: {platform_tokens.get('expired', 0)}")
            
            accounts = platform_accounts.get('accounts', {})
            for account_name, account_info in accounts.items():
                status_icon = "✅" if account_info.get('authorized') else "❌"
                print(f"   {status_icon} {account_name}")
                
                if account_info.get('expires_at'):
                    print(f"      🕒 Токен истекает: {account_info['expires_at']}")
                if account_info.get('last_refreshed'):
                    print(f"      🔄 Последнее обновление: {account_info['last_refreshed']}")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса: {e}")


def authorize_accounts(auto_poster: SocialMediaAutoPoster):
    """Авторизовать аккаунты."""
    print("\n🔐 Авторизация аккаунтов")
    print("1. Авторизовать все аккаунты")
    print("2. Авторизовать аккаунты конкретной платформы")
    print("3. Авторизовать конкретный аккаунт")
    
    choice = input("👉 Выберите вариант (1-3): ").strip()
    
    try:
        if choice == "1":
            print("\n🔐 Авторизация всех аккаунтов...")
            results = auto_poster.authorize_all_accounts()
            
            for platform, accounts in results.items():
                print(f"\n📱 {platform.upper()}:")
                for account_name, result in accounts.items():
                    if result.get('success'):
                        print(f"   ✅ {account_name} - успешно авторизован")
                    else:
                        print(f"   ❌ {account_name} - ошибка: {result.get('error')}")
        
        elif choice == "2":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            if platform in ['instagram', 'tiktok', 'youtube']:
                print(f"\n🔐 Авторизация всех аккаунтов {platform}...")
                results = auto_poster.authorize_all_accounts(platform)
                
                accounts = results.get(platform, {})
                for account_name, result in accounts.items():
                    if result.get('success'):
                        print(f"   ✅ {account_name} - успешно авторизован")
                    else:
                        print(f"   ❌ {account_name} - ошибка: {result.get('error')}")
            else:
                print("❌ Неверная платформа")
        
        elif choice == "3":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            account = input("👉 Введите имя аккаунта: ").strip()
            
            if platform in ['instagram', 'tiktok', 'youtube'] and account:
                print(f"\n🔐 Авторизация {platform}:{account}...")
                result = auto_poster.authorize_account(platform, account)
                
                if result.get('success'):
                    print(f"✅ Аккаунт {platform}:{account} успешно авторизован")
                    if result.get('expires_in'):
                        print(f"   🕒 Токен действителен {result['expires_in']} секунд")
                else:
                    print(f"❌ Ошибка авторизации: {result.get('error')}")
            else:
                print("❌ Неверные данные")
        
    except Exception as e:
        print(f"❌ Ошибка при авторизации: {e}")


def refresh_tokens(auto_poster: SocialMediaAutoPoster):
    """Обновить токены."""
    print("\n🔄 Обновление токенов")
    print("1. Обновить все токены")
    print("2. Обновить токены конкретной платформы")
    print("3. Обновить токен конкретного аккаунта")
    
    choice = input("👉 Выберите вариант (1-3): ").strip()
    
    try:
        if choice == "1":
            print("\n🔄 Обновление всех токенов...")
            results = auto_poster.refresh_account_tokens()
            
        elif choice == "2":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            if platform in ['instagram', 'tiktok', 'youtube']:
                print(f"\n🔄 Обновление токенов {platform}...")
                results = auto_poster.refresh_account_tokens(platform=platform)
            else:
                print("❌ Неверная платформа")
                return
        
        elif choice == "3":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            account = input("👉 Введите имя аккаунта: ").strip()
            
            if platform in ['instagram', 'tiktok', 'youtube'] and account:
                print(f"\n🔄 Обновление токена {platform}:{account}...")
                results = auto_poster.refresh_account_tokens(platform=platform, account_name=account)
            else:
                print("❌ Неверные данные")
                return
        else:
            print("❌ Неверный выбор")
            return
        
        # Показать результаты
        for account_key, success in results.items():
            if success:
                print(f"✅ {account_key} - токен обновлен")
            else:
                print(f"❌ {account_key} - не удалось обновить токен")
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении токенов: {e}")


def validate_accounts(auto_poster: SocialMediaAutoPoster):
    """Валидировать аккаунты."""
    print("\n✅ Валидация аккаунтов...")
    
    try:
        results = auto_poster.validate_all_accounts_extended()
        
        for platform, accounts in results.items():
            print(f"\n📱 {platform.upper()}:")
            
            for account_name, account_info in accounts.items():
                if account_info.get('valid'):
                    print(f"   ✅ {account_name} - валиден")
                else:
                    print(f"   ❌ {account_name} - невалиден")
                    if account_info.get('error'):
                        print(f"      🚫 Ошибка: {account_info['error']}")
                    
                    print(f"      📋 Детали:")
                    print(f"         Включен: {account_info.get('enabled', False)}")
                    print(f"         Есть токен: {account_info.get('has_token', False)}")
                    print(f"         Токен валиден: {account_info.get('token_valid', False)}")
        
    except Exception as e:
        print(f"❌ Ошибка при валидации: {e}")


def post_immediately(auto_poster: SocialMediaAutoPoster):
    """Опубликовать контент немедленно."""
    print("\n📤 Немедленная публикация контента")
    
    # Получить путь к видео
    video_path = input("👉 Введите путь к видео файлу: ").strip()
    if not video_path or not Path(video_path).exists():
        print("❌ Файл не найден")
        return
    
    # Получить подпись
    caption = input("👉 Введите подпись к посту: ").strip()
    if not caption:
        caption = "Автоматический пост"
    
    # Выбрать платформы
    print("\n📱 Выберите платформы для публикации:")
    print("1. Instagram")
    print("2. TikTok") 
    print("3. YouTube")
    print("4. Все платформы")
    
    platform_choice = input("👉 Введите номера через запятую (1,2,3) или 4 для всех: ").strip()
    
    platforms = []
    if "4" in platform_choice:
        platforms = ["instagram", "tiktok", "youtube"]
    else:
        if "1" in platform_choice:
            platforms.append("instagram")
        if "2" in platform_choice:
            platforms.append("tiktok")
        if "3" in platform_choice:
            platforms.append("youtube")
    
    if not platforms:
        print("❌ Не выбрана ни одна платформа")
        return
    
    # Выбрать аккаунты (опционально)
    use_specific_accounts = input("👉 Использовать конкретные аккаунты? (y/n): ").strip().lower()
    accounts = None
    
    if use_specific_accounts == 'y':
        account_names = input("👉 Введите имена аккаунтов через запятую: ").strip()
        if account_names:
            accounts = [name.strip() for name in account_names.split(',')]
    
    try:
        print(f"\n📤 Публикация на платформы: {', '.join(platforms)}")
        if accounts:
            print(f"📋 Аккаунты: {', '.join(accounts)}")
        
        result = auto_poster.post_immediately(
            content_path=video_path,
            platforms=platforms,
            caption=caption,
            accounts=accounts
        )
        
        print(f"\n📊 РЕЗУЛЬТАТЫ ПУБЛИКАЦИИ:")
        print(f"   ✅ Успешных постов: {result['successful_posts']}")
        print(f"   ❌ Неудачных постов: {result['failed_posts']}")
        
        print(f"\n📋 ДЕТАЛИ:")
        for post_result in result.get('results', []):
            platform = post_result['platform']
            account = post_result['account']
            success = post_result['success']
            
            if success:
                post_id = post_result.get('post_id', 'N/A')
                print(f"   ✅ {platform}:{account} - ID: {post_id}")
            else:
                error = post_result.get('error', 'Unknown error')
                print(f"   ❌ {platform}:{account} - Ошибка: {error}")
        
    except Exception as e:
        print(f"❌ Ошибка при публикации: {e}")


def schedule_post(auto_poster: SocialMediaAutoPoster):
    """Запланировать публикацию."""
    print("\n⏰ Планирование публикации")
    
    # Получить путь к видео
    video_path = input("👉 Введите путь к видео файлу: ").strip()
    if not video_path or not Path(video_path).exists():
        print("❌ Файл не найден")
        return
    
    # Получить подпись
    caption = input("👉 Введите подпись к посту: ").strip()
    if not caption:
        caption = "Запланированный пост"
    
    # Выбрать платформы
    print("\n📱 Выберите платформы для публикации:")
    print("1. Instagram")
    print("2. TikTok")
    print("3. YouTube") 
    print("4. Все платформы")
    
    platform_choice = input("👉 Введите номера через запятую (1,2,3) или 4 для всех: ").strip()
    
    platforms = []
    if "4" in platform_choice:
        platforms = ["instagram", "tiktok", "youtube"]
    else:
        if "1" in platform_choice:
            platforms.append("instagram")
        if "2" in platform_choice:
            platforms.append("tiktok")
        if "3" in platform_choice:
            platforms.append("youtube")
    
    if not platforms:
        print("❌ Не выбрана ни одна платформа")
        return
    
    # Выбрать время
    print("\n⏰ Выберите время публикации:")
    print("1. Через 1 час")
    print("2. Через 6 часов")
    print("3. Завтра в это же время")
    print("4. Указать конкретное время")
    print("5. Случайное время (по расписанию)")
    
    time_choice = input("👉 Выберите вариант (1-5): ").strip()
    
    scheduled_time = None
    
    if time_choice == "1":
        scheduled_time = datetime.now() + timedelta(hours=1)
    elif time_choice == "2":
        scheduled_time = datetime.now() + timedelta(hours=6)
    elif time_choice == "3":
        scheduled_time = datetime.now() + timedelta(days=1)
    elif time_choice == "4":
        time_str = input("👉 Введите время (YYYY-MM-DD HH:MM): ").strip()
        try:
            scheduled_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            print("❌ Неверный формат времени")
            return
    # Для варианта 5 оставляем scheduled_time = None (случайное время)
    
    try:
        print(f"\n⏰ Планирование публикации...")
        if scheduled_time:
            print(f"   🕒 Время: {scheduled_time}")
        else:
            print(f"   🎲 Время: случайное (по расписанию)")
        
        scheduled_ids = auto_poster.schedule_post(
            content_path=video_path,
            platforms=platforms,
            caption=caption,
            scheduled_time=scheduled_time
        )
        
        print(f"\n✅ Запланировано постов: {len(scheduled_ids)}")
        for post_id in scheduled_ids:
            print(f"   📋 ID поста: {post_id}")
        
    except Exception as e:
        print(f"❌ Ошибка при планировании: {e}")


def show_scheduled_posts(auto_poster: SocialMediaAutoPoster):
    """Показать запланированные посты."""
    print("\n📋 Запланированные посты")
    
    try:
        scheduled_posts = auto_poster.get_scheduled_posts()
        
        if not scheduled_posts:
            print("📭 Нет запланированных постов")
            return
        
        print(f"📊 Всего запланировано: {len(scheduled_posts)}")
        
        for post in scheduled_posts:
            print(f"\n📄 Пост ID: {post.id}")
            print(f"   📱 Платформа: {post.platform}")
            print(f"   👤 Аккаунт: {post.account}")
            print(f"   🕒 Время: {post.scheduled_time}")
            print(f"   📁 Файл: {post.content_path}")
            print(f"   📝 Подпись: {post.caption[:50]}{'...' if len(post.caption) > 50 else ''}")
            print(f"   🔄 Попыток: {post.retry_count}")
            print(f"   📊 Статус: {post.status}")
        
        # Опции управления
        print(f"\n🛠️ Управление постами:")
        print("1. Отменить пост")
        print("2. Показать статистику")
        print("0. Назад")
        
        choice = input("👉 Выберите действие: ").strip()
        
        if choice == "1":
            post_id = input("👉 Введите ID поста для отмены: ").strip()
            if post_id:
                success = auto_poster.cancel_post(post_id)
                if success:
                    print(f"✅ Пост {post_id} отменен")
                else:
                    print(f"❌ Не удалось отменить пост {post_id}")
        
        elif choice == "2":
            stats = auto_poster.get_posting_stats()
            print(f"\n📊 СТАТИСТИКА ПОСТОВ:")
            print(f"   📤 Всего отправлено: {stats.get('total_posts', 0)}")
            print(f"   ✅ Успешных: {stats.get('successful_posts', 0)}")
            print(f"   ❌ Неудачных: {stats.get('failed_posts', 0)}")
            print(f"   ⏰ Запланированных: {stats.get('scheduled_posts', 0)}")
        
    except Exception as e:
        print(f"❌ Ошибка при получении постов: {e}")


def manage_tokens(auto_poster: SocialMediaAutoPoster):
    """Управление токенами."""
    print("\n🛠️ Управление токенами")
    print("1. Показать информацию о токене")
    print("2. Добавить токен вручную")
    print("3. Удалить токен")
    print("4. Получить URL авторизации")
    
    choice = input("👉 Выберите действие (1-4): ").strip()
    
    try:
        if choice == "1":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            account = input("👉 Введите имя аккаунта: ").strip()
            
            if platform in ['instagram', 'tiktok', 'youtube'] and account:
                info = auto_poster.get_account_token_info(platform, account)
                
                if info:
                    print(f"\n📊 ИНФОРМАЦИЯ О ТОКЕНЕ:")
                    print(f"   📱 Платформа: {info['platform']}")
                    print(f"   👤 Аккаунт: {info['account_name']}")
                    print(f"   🔄 Есть refresh токен: {info['has_refresh_token']}")
                    print(f"   🕒 Истекает: {info['expires_at'] or 'Никогда'}")
                    print(f"   📅 Создан: {info['created_at'] or 'Неизвестно'}")
                    print(f"   🔄 Последнее обновление: {info['last_refreshed'] or 'Никогда'}")
                    print(f"   ⚠️ Истек: {'Да' if info['is_expired'] else 'Нет'}")
                    
                    if info.get('scope'):
                        print(f"   🔐 Права доступа: {info['scope']}")
                else:
                    print(f"❌ Токен не найден для {platform}:{account}")
        
        elif choice == "2":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            account = input("👉 Введите имя аккаунта: ").strip()
            access_token = input("👉 Введите токен доступа: ").strip()
            refresh_token = input("👉 Введите токен обновления (опционально): ").strip() or None
            expires_str = input("👉 Введите время жизни в секундах (опционально): ").strip()
            
            expires_in = None
            if expires_str:
                try:
                    expires_in = int(expires_str)
                except ValueError:
                    print("❌ Неверное время жизни")
                    return
            
            if platform in ['instagram', 'tiktok', 'youtube'] and account and access_token:
                success = auto_poster.add_account_token(
                    platform=platform,
                    account_name=account,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_in=expires_in
                )
                
                if success:
                    print(f"✅ Токен добавлен для {platform}:{account}")
                else:
                    print(f"❌ Не удалось добавить токен для {platform}:{account}")
        
        elif choice == "3":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            account = input("👉 Введите имя аккаунта: ").strip()
            
            if platform in ['instagram', 'tiktok', 'youtube'] and account:
                confirm = input(f"⚠️ Удалить токен для {platform}:{account}? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    success = auto_poster.remove_account_token(platform, account)
                    
                    if success:
                        print(f"✅ Токен удален для {platform}:{account}")
                    else:
                        print(f"❌ Не удалось удалить токен для {platform}:{account}")
        
        elif choice == "4":
            platform = input("👉 Введите платформу (instagram/tiktok/youtube): ").strip().lower()
            account = input("👉 Введите имя аккаунта: ").strip()
            
            if platform in ['instagram', 'tiktok', 'youtube'] and account:
                url = auto_poster.get_account_authorization_url(platform, account)
                
                if url:
                    print(f"\n🔗 URL АВТОРИЗАЦИИ:")
                    print(f"{url}")
                    print("\n📋 Скопируйте ссылку и откройте в браузере")
                else:
                    print("❌ Не удалось получить URL авторизации")
        
    except Exception as e:
        print(f"❌ Ошибка при управлении токенами: {e}")


def show_system_info(auto_poster: SocialMediaAutoPoster):
    """Показать подробную информацию о системе."""
    print("\n🔍 ПОДРОБНАЯ ИНФОРМАЦИЯ О СИСТЕМЕ")
    
    try:
        system_status = auto_poster.get_system_status()
        
        print(f"\n🖥️ СТАТУС СИСТЕМЫ:")
        print(f"   📋 Конфигурация загружена: {system_status.get('config_loaded', False)}")
        print(f"   ⏰ Планировщик работает: {system_status.get('scheduler_running', False)}")
        print(f"   📤 Запланированных постов: {system_status.get('scheduled_posts_count', 0)}")
        
        print(f"\n🔌 API КЛИЕНТЫ:")
        api_clients = system_status.get('api_clients', {})
        for platform, status in api_clients.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {platform.upper()}")
        
        print(f"\n📬 УВЕДОМЛЕНИЯ:")
        notifications = system_status.get('notification_status', {})
        for channel, status in notifications.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {channel.upper()}")
        
        # Тестирование уведомлений
        test_notifications = input("\n👉 Протестировать уведомления? (y/n): ").strip().lower()
        if test_notifications == 'y':
            print("\n📧 Тестирование уведомлений...")
            test_results = auto_poster.test_notifications()
            
            for channel, success in test_results.items():
                if success:
                    print(f"   ✅ {channel.upper()} - тест прошел")
                else:
                    print(f"   ❌ {channel.upper()} - тест не прошел")
        
    except Exception as e:
        print(f"❌ Ошибка при получении информации: {e}")


if __name__ == "__main__":
    main()
