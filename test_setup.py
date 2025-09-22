#!/usr/bin/env python3
"""
Быстрый тест настройки множественных аккаунтов.
"""

import sys
from pathlib import Path

# Добавить путь к модулям
sys.path.append(str(Path(__file__).parent / "src"))

from src.auto_poster import SocialMediaAutoPoster


def test_setup():
    """Проверить текущую настройку системы."""
    
    print("🧪 ТЕСТ НАСТРОЙКИ МНОЖЕСТВЕННЫХ АККАУНТОВ")
    print("=" * 50)
    
    try:
        # Инициализировать систему
        print("1. Инициализация системы...")
        auto_poster = SocialMediaAutoPoster()
        print("   ✅ Система инициализирована")
        
        # Проверить статус системы
        print("\n2. Проверка статуса системы...")
        system_status = auto_poster.get_system_status()
        
        print(f"   📋 Конфигурация загружена: {system_status.get('config_loaded', False)}")
        print(f"   🔌 API клиенты: {len(system_status.get('api_clients', {}))}")
        
        # Проверить аккаунты
        print("\n3. Проверка аккаунтов...")
        account_status = system_status.get('account_status', {})
        
        total_accounts = account_status.get('total_accounts', 0)
        authorized_accounts = account_status.get('authorized_accounts', 0)
        
        print(f"   👥 Всего аккаунтов в конфиге: {total_accounts}")
        print(f"   ✅ Авторизованных аккаунтов: {authorized_accounts}")
        
        if total_accounts == 0:
            print("\n   ⚠️  НЕТ НАСТРОЕННЫХ АККАУНТОВ")
            print("   📝 Необходимо:")
            print("      1. Обновить config.yaml с реальными данными")
            print("      2. Включить аккаунты (enabled: true)")
            print("      3. Запустить: python account_manager.py authorize --all")
            return False
        
        # Детали по платформам
        print("\n4. Детали по платформам:")
        platforms = account_status.get('platforms', {})
        
        for platform, info in platforms.items():
            total = info.get('total', 0)
            authorized = info.get('authorized', 0)
            
            if total > 0:
                print(f"   📱 {platform.upper()}: {authorized}/{total} авторизованных")
                
                # Показать аккаунты
                accounts = info.get('accounts', {})
                for acc_name, acc_info in accounts.items():
                    status_icon = "✅" if acc_info.get('authorized') else "❌"
                    print(f"      {status_icon} {acc_name}")
        
        # Проверить токены
        print("\n5. Проверка токенов...")
        token_status = system_status.get('token_status', {})
        
        total_tokens = token_status.get('total_tokens', 0)
        valid_tokens = token_status.get('valid_tokens', 0)
        expired_tokens = token_status.get('expired_tokens', 0)
        
        print(f"   🎫 Всего токенов: {total_tokens}")
        print(f"   ✅ Действительных: {valid_tokens}")
        print(f"   ⚠️  Истекших: {expired_tokens}")
        
        # Рекомендации
        print("\n6. Рекомендации:")
        
        if authorized_accounts == 0:
            print("   🔐 Запустите авторизацию:")
            print("      python account_manager.py authorize --all")
        
        elif authorized_accounts < total_accounts:
            print("   🔐 Авторизуйте оставшиеся аккаунты:")
            print("      python account_manager.py authorize --all")
        
        elif expired_tokens > 0:
            print("   🔄 Обновите истекшие токены:")
            print("      python account_manager.py refresh")
        
        else:
            print("   🎉 Все готово к использованию!")
            print("   📤 Можете публиковать контент:")
            print("      python main.py post 'video.mp4' --caption 'Test post'")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


def show_next_steps():
    """Показать следующие шаги."""
    
    print("\n" + "=" * 50)
    print("📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("=" * 50)
    
    print("\n1. 📝 Настройте config.yaml:")
    print("   - Замените тестовые данные на реальные app_id/client_secret")
    print("   - Установите enabled: true для нужных аккаунтов")
    print("   - Включите платформы (platforms -> enabled: true)")
    
    print("\n2. 🔐 Авторизуйте аккаунты:")
    print("   python account_manager.py authorize --all")
    
    print("\n3. ✅ Проверьте статус:")
    print("   python account_manager.py status")
    
    print("\n4. 📤 Протестируйте публикацию:")
    print("   python main.py post 'path/to/video.mp4' --caption 'Test'")
    
    print("\n5. 🎮 Используйте интерактивный интерфейс:")
    print("   python example_multiple_accounts.py")


if __name__ == "__main__":
    success = test_setup()
    show_next_steps()
    
    if success:
        print("\n🎯 Система готова к настройке!")
    else:
        print("\n⚠️  Требуется дополнительная настройка")
