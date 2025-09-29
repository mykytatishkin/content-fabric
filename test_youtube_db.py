#!/usr/bin/env python3
"""
Test script for YouTube database integration.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.database import get_database
from src.api_clients.youtube_db_client import YouTubeDBClient


def test_database():
    """Test database functionality."""
    print("🧪 Тестирование базы данных...")
    
    db = get_database()
    
    # Test adding channels
    print("\n1. Добавление каналов...")
    success1 = db.add_channel(
        name="Teasera",
        channel_id="teasera-git",
        client_id="test_client_id_1",
        client_secret="test_client_secret_1",
        enabled=True
    )
    print(f"   Teasera: {'✅' if success1 else '❌'}")
    
    success2 = db.add_channel(
        name="Andrew Garle",
        channel_id="@AndrewGarle",
        client_id="test_client_id_2",
        client_secret="test_client_secret_2",
        enabled=True
    )
    print(f"   Andrew Garle: {'✅' if success2 else '❌'}")
    
    # Test listing channels
    print("\n2. Список каналов...")
    channels = db.get_all_channels()
    for channel in channels:
        status = "✅" if channel.enabled else "❌"
        print(f"   {status} {channel.name} (ID: {channel.channel_id})")
    
    # Test getting specific channel
    print("\n3. Получение канала...")
    channel = db.get_channel("Teasera")
    if channel:
        print(f"   ✅ Найден канал: {channel.name}")
    else:
        print("   ❌ Канал не найден")
    
    # Test token management
    print("\n4. Управление токенами...")
    from datetime import datetime, timedelta
    expires_at = datetime.now() + timedelta(hours=1)
    
    success = db.update_channel_tokens(
        "Teasera",
        "test_access_token",
        "test_refresh_token",
        expires_at
    )
    print(f"   Обновление токенов: {'✅' if success else '❌'}")
    
    # Test token expiration
    is_expired = db.is_token_expired("Teasera")
    print(f"   Токен истек: {'❌' if is_expired else '✅'}")
    
    print("\n✅ Тестирование базы данных завершено!")


def test_youtube_client():
    """Test YouTube client with database."""
    print("\n🧪 Тестирование YouTube клиента...")
    
    client = YouTubeDBClient()
    
    # Test getting available channels
    print("\n1. Доступные каналы...")
    channels = client.get_available_channels()
    print(f"   Найдено каналов: {len(channels)}")
    for channel in channels:
        print(f"   - {channel}")
    
    # Test setting channel
    if channels:
        print(f"\n2. Установка канала '{channels[0]}'...")
        success = client.set_channel(channels[0])
        print(f"   Результат: {'✅' if success else '❌'}")
        
        if success:
            # Test getting channel info
            print(f"\n3. Информация о канале...")
            info = client.get_channel_info()
            if info:
                print(f"   ✅ Канал: {info.get('title', 'Unknown')}")
                print(f"   Подписчики: {info.get('subscriber_count', '0')}")
            else:
                print("   ❌ Не удалось получить информацию о канале")
    
    print("\n✅ Тестирование YouTube клиента завершено!")


def main():
    """Main test function."""
    print("🚀 Запуск тестов YouTube Database Integration")
    print("=" * 50)
    
    try:
        test_database()
        test_youtube_client()
        
        print("\n" + "=" * 50)
        print("🎉 Все тесты завершены!")
        
    except Exception as e:
        print(f"\n❌ Ошибка во время тестирования: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
