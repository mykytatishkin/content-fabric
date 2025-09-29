#!/usr/bin/env python3
"""
Migration script to move YouTube channels from config.yaml to database.
"""

import sys
import yaml
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.database import get_database


def migrate_channels():
    """Migrate channels from config.yaml to database."""
    print("🔄 Миграция каналов из config.yaml в базу данных...")
    
    # Load config
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("❌ Файл config.yaml не найден")
        return False
    
    # Get YouTube accounts
    youtube_accounts = config.get('accounts', {}).get('youtube', [])
    if not youtube_accounts:
        print("📭 YouTube каналы не найдены в config.yaml")
        return False
    
    # Initialize database
    db = get_database()
    
    migrated_count = 0
    skipped_count = 0
    
    print(f"\n📋 Найдено {len(youtube_accounts)} каналов для миграции:")
    
    for account in youtube_accounts:
        name = account.get('name')
        channel_id = account.get('channel_id', '')
        client_id = account.get('client_id', '')
        client_secret = account.get('client_secret', '')
        enabled = account.get('enabled', True)
        
        print(f"\n  📺 {name}:")
        print(f"     ID: {channel_id}")
        print(f"     Client ID: {client_id[:20]}..." if client_id else "     Client ID: Не указан")
        print(f"     Статус: {'✅ Включен' if enabled else '❌ Отключен'}")
        
        # Check if channel already exists
        existing = db.get_channel(name)
        if existing:
            print(f"     ⚠️ Канал уже существует в БД - пропускаем")
            skipped_count += 1
            continue
        
        # Add to database
        success = db.add_channel(name, channel_id, client_id, client_secret, enabled)
        if success:
            print(f"     ✅ Успешно добавлен в БД")
            migrated_count += 1
        else:
            print(f"     ❌ Ошибка при добавлении в БД")
            skipped_count += 1
    
    print(f"\n📊 Результаты миграции:")
    print(f"   ✅ Мигрировано: {migrated_count}")
    print(f"   ⚠️ Пропущено: {skipped_count}")
    print(f"   📋 Всего: {len(youtube_accounts)}")
    
    if migrated_count > 0:
        print(f"\n🎉 Миграция завершена! Теперь вы можете:")
        print(f"   1. Использовать youtube_db_manager.py для управления каналами")
        print(f"   2. Публиковать на несколько каналов одновременно")
        print(f"   3. Управлять токенами через базу данных")
    
    return migrated_count > 0


def show_next_steps():
    """Show next steps after migration."""
    print(f"\n📋 Следующие шаги:")
    print(f"   1. Обновите .env файл с реальными credentials:")
    print(f"      YOUTUBE_TEASERA_CLIENT_ID=ваш_client_id")
    print(f"      YOUTUBE_TEASERA_CLIENT_SECRET=ваш_client_secret")
    print(f"      YOUTUBE_ANDREW_CLIENT_ID=ваш_client_id")
    print(f"      YOUTUBE_ANDREW_CLIENT_SECRET=ваш_client_secret")
    print(f"   2. Поместите credentials.json в корень проекта")
    print(f"   3. Протестируйте авторизацию:")
    print(f"      python3 youtube_db_manager.py list")
    print(f"   4. Публикуйте на несколько каналов:")
    print(f"      python3 main.py post --platforms youtube --accounts 'Teasera,Andrew Garle'")


def main():
    """Main migration function."""
    print("🚀 YouTube Database Migration Tool")
    print("=" * 50)
    
    try:
        success = migrate_channels()
        
        if success:
            show_next_steps()
        else:
            print("\n❌ Миграция не выполнена")
        
    except Exception as e:
        print(f"\n❌ Ошибка во время миграции: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
