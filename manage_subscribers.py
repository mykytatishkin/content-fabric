#!/usr/bin/env python3
"""
Manage Telegram Subscribers - додавання/видалення підписників на розсилку.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.utils.telegram_broadcast import TelegramBroadcast


def main():
    broadcaster = TelegramBroadcast()
    
    if len(sys.argv) < 2:
        print("="*60)
        print("Telegram Auto-Broadcast Manager")
        print("="*60)
        print()
        print("ℹ️  Всі хто натиснув /start автоматично отримують розсилку")
        print()
        print("Команди:")
        print("  list     - Показати всіх користувачів")
        print("  sync     - Синхронізувати нових користувачів")
        print("  test     - Відправити тестове повідомлення")
        print()
        print(f"Поточна кількість користувачів: {len(broadcaster.get_subscribers())}")
        print()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        subscribers = broadcaster.get_subscribers()
        print(f"\n📋 Користувачі які отримують розсилку ({len(subscribers)}):")
        if subscribers:
            for i, chat_id in enumerate(subscribers, 1):
                print(f"  {i}. {chat_id}")
        else:
            print("  Ще немає користувачів")
            print("  👉 Хтось має натиснути /start у боті")
        print()
    
    elif command == "sync":
        print("🔄 Синхронізація нових користувачів...")
        new_count = broadcaster.process_start_commands()
        total = broadcaster.auto_sync_users()
        if new_count > 0:
            print(f"✅ Додано {new_count} нових користувачів")
        else:
            print("ℹ️ Нових користувачів немає")
        print(f"📊 Всього користувачів: {total}")
    
    elif command == "test":
        # Спочатку синхронізуємо
        broadcaster.process_start_commands()
        subscribers = broadcaster.get_subscribers()
        
        if not subscribers:
            print("❌ Немає користувачів для тесту")
            print("👉 Натисніть /start у боті")
            return
        
        test_message = "🧪 **Тестове повідомлення**\n\nЯкщо ви бачите це - автоматична розсилка працює!\n\nЩоденні звіти будуть приходити о 12:00."
        print(f"📤 Відправка тестового повідомлення {len(subscribers)} користувачам...")
        
        result = broadcaster.broadcast_message(test_message)
        print(f"\n✅ Успішно: {result['success']}/{result['total']}")
        if result['failed'] > 0:
            print(f"❌ Помилки: {result['failed']}")
    
    else:
        print(f"❌ Невідома команда: {command}")
        print("Використайте: list, sync, test")


if __name__ == "__main__":
    main()

