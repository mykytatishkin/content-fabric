#!/usr/bin/env python3
"""
Script to check which Google Cloud Console is used for publishing for each channel.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.database.mysql_db import get_mysql_database
from core.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Check which Google consoles are used for publishing."""
    db = None
    try:
        print("\n" + "="*80)
        print("📊 ПРОВЕРКА GOOGLE КОНСОЛЕЙ ДЛЯ ПУБЛИКАЦИЙ")
        print("="*80 + "\n")
        
        db = get_mysql_database()
        
        # Get all Google consoles
        consoles = db.get_all_google_consoles(enabled_only=False)
        
        if not consoles:
            print("⚠️  В базе данных нет настроенных Google Cloud Console проектов")
            print("   Публикации будут использовать credentials из самих каналов (fallback)\n")
        else:
            print(f"📱 Найдено Google Cloud Console проектов: {len(consoles)}\n")
            
            for console in consoles:
                status = "✅ Включена" if console.enabled else "❌ Отключена"
                print(f"  {status} | {console.name}")
                if console.description:
                    print(f"      Описание: {console.description}")
                print(f"      ID проекта: {console.client_id[:30]}..." if console.client_id else "      ID проекта: не указан")
                print()
        
        # Get all channels and their REAL console usage (as it happens in publishing)
        channels = db.get_all_channels(enabled_only=False)
        
        print("\n" + "-"*80)
        print("📺 РЕАЛЬНО ИСПОЛЬЗУЕМЫЕ КОНСОЛИ ПРИ ПУБЛИКАЦИИ")
        print("-"*80 + "\n")
        print("💡 Это те консоли, которые РЕАЛЬНО используются в коде при публикации")
        print("   (через get_console_credentials_for_channel -> account_info -> _create_service_with_token)\n")
        
        if not channels:
            print("⚠️  В базе данных нет каналов\n")
        else:
            # Create a map of client_id -> console_name for quick lookup
            client_id_to_console = {}
            for console in consoles:
                if console.client_id:
                    client_id_to_console[console.client_id] = console.name
            
            for channel in channels:
                status = "✅ Включен" if channel.enabled else "❌ Отключен"
                print(f"{status} | {channel.name}")
                print(f"   Channel ID: {channel.channel_id}")
                
                # Get REAL credentials that will be used (same as in task_worker.py line 190)
                credentials = db.get_console_credentials_for_channel(channel.name)
                
                if credentials:
                    real_client_id = credentials['client_id']
                    
                    # Try to identify which console this client_id belongs to
                    console_name_by_id = client_id_to_console.get(real_client_id)
                    
                    if console_name_by_id:
                        # This client_id matches a console in the database
                        console = db.get_google_console(console_name_by_id)
                        console_status = "✅ Включена" if console and console.enabled else "❌ Отключена"
                        print(f"   🎯 РЕАЛЬНО ИСПОЛЬЗУЕТСЯ КОНСОЛЬ: {console_name_by_id} ({console_status})")
                        if console and console.description:
                            print(f"      Описание: {console.description}")
                        print(f"      Client ID: {real_client_id[:50]}...")
                    elif channel.console_name:
                        # Channel has console_name but client_id doesn't match - possible mismatch
                        console = db.get_google_console(channel.console_name)
                        if console and console.client_id != real_client_id:
                            print(f"   ⚠️  КОНФЛИКТ: У канала указана консоль '{channel.console_name}'")
                            print("      Но реально используется другой client_id!")
                            print(f"      Ожидалось: {console.client_id[:50]}...")
                            print(f"      Используется: {real_client_id[:50]}...")
                        else:
                            print(f"   🎯 РЕАЛЬНО ИСПОЛЬЗУЕТСЯ КОНСОЛЬ: {channel.console_name}")
                            print(f"      Client ID: {real_client_id[:50]}...")
                    else:
                        # Fallback - using channel's own credentials
                        print("   📝 РЕАЛЬНО ИСПОЛЬЗУЕТСЯ: Fallback (credentials из самого канала)")
                        print(f"      Client ID: {real_client_id[:50]}...")
                        print("      ⚠️  Это означает, что у канала нет назначенной консоли")
                else:
                    print("   ❌ ОШИБКА: Credentials НЕ найдены - публикация НЕВОЗМОЖНА!")
                    if not channel.console_name and not (channel.client_id and channel.client_secret):
                        print("      У канала нет ни console_name, ни client_id/client_secret")
                
                print()
        
        # Summary - based on REAL usage
        print("\n" + "="*80)
        print("📋 СВОДКА (по реальному использованию)")
        print("="*80 + "\n")
        
        enabled_consoles = [c for c in consoles if c.enabled]
        enabled_channels = [c for c in channels if c.enabled]
        
        # Count REAL console usage (what actually gets used in publishing)
        real_console_usage = {}
        real_fallback_count = 0
        real_no_credentials = 0
        
        client_id_to_console = {}
        for console in consoles:
            if console.client_id:
                client_id_to_console[console.client_id] = console.name
        
        for channel in channels:
            credentials = db.get_console_credentials_for_channel(channel.name)
            if credentials:
                real_client_id = credentials['client_id']
                console_name_by_id = client_id_to_console.get(real_client_id)
                if console_name_by_id:
                    real_console_usage[console_name_by_id] = real_console_usage.get(console_name_by_id, 0) + 1
                else:
                    real_fallback_count += 1
            else:
                real_no_credentials += 1
        
        print(f"✅ Включенных консолей: {len(enabled_consoles)}")
        print(f"✅ Включенных каналов: {len(enabled_channels)}")
        print()
        print("🎯 РЕАЛЬНОЕ использование консолей при публикации:")
        if real_console_usage:
            for console_name, count in sorted(real_console_usage.items(), key=lambda x: x[1], reverse=True):
                console = db.get_google_console(console_name)
                status = "✅" if console and console.enabled else "❌"
                print(f"   {status} {console_name}: {count} канал(ов)")
        else:
            print("   (нет каналов, использующих консоли)")
        print()
        print(f"📝 Каналов с fallback (credentials из канала): {real_fallback_count}")
        print(f"❌ Каналов без credentials (публикация невозможна): {real_no_credentials}")
        print()
        
    except Exception as e:
        logger.error(f"Ошибка при проверке консолей: {e}", exc_info=True)
        print(f"\n❌ Ошибка: {e}\n")
        return 1
    finally:
        if db:
            db.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

