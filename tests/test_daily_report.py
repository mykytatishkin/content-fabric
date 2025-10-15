#!/usr/bin/env python3
"""
Quick test script for Daily Report System.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.utils.daily_report import DailyReportManager
from core.utils.notifications import NotificationManager
from core.database.mysql_db import YouTubeMySQLDatabase


def test_1_telegram_connection():
    """Test 1: Перевірка Telegram підключення."""
    print("\n" + "="*60)
    print("Test 1: Telegram Connection")
    print("="*60)
    
    try:
        notifier = NotificationManager()
        status = notifier.get_notification_status()
        
        print(f"Telegram Enabled: {status['telegram_enabled']}")
        print(f"Telegram Configured: {status['telegram_configured']}")
        
        if status['telegram_configured']:
            print("✅ Telegram налаштовано правильно")
            return True
        else:
            print("❌ Telegram не налаштовано")
            return False
            
    except Exception as e:
        print(f"❌ Помилка: {str(e)}")
        return False


def test_2_database_connection():
    """Test 2: Перевірка підключення до БД."""
    print("\n" + "="*60)
    print("Test 2: Database Connection")
    print("="*60)
    
    try:
        db = YouTubeMySQLDatabase()
        stats = db.get_database_stats()
        
        print(f"Total Channels: {stats.get('total_channels', 0)}")
        print(f"Total Tasks: {stats.get('total_tasks', 0)}")
        print(f"Pending Tasks: {stats.get('pending_tasks', 0)}")
        
        if stats:
            print("✅ БД підключено успішно")
            return True
        else:
            print("❌ Помилка підключення до БД")
            return False
            
    except Exception as e:
        print(f"❌ Помилка: {str(e)}")
        return False


def test_3_get_tasks():
    """Test 3: Перевірка наявності tasks за вчора."""
    print("\n" + "="*60)
    print("Test 3: Yesterday's Tasks")
    print("="*60)
    
    try:
        manager = DailyReportManager()
        yesterday = datetime.now() - timedelta(days=1)
        tasks = manager._get_tasks_for_date(yesterday)
        
        print(f"Date: {yesterday.strftime('%Y-%m-%d')}")
        print(f"Tasks Found: {len(tasks)}")
        
        if tasks:
            # Show task breakdown
            status_map = {0: 'Pending', 1: 'Completed', 2: 'Failed', 3: 'Processing'}
            status_counts = {}
            
            for task in tasks:
                status_name = status_map.get(task.status, 'Unknown')
                status_counts[status_name] = status_counts.get(status_name, 0) + 1
            
            print("\nTask Breakdown:")
            for status, count in status_counts.items():
                emoji = "✅" if status == "Completed" else "❌" if status == "Failed" else "⏳"
                print(f"  {emoji} {status}: {count}")
            
            print(f"\n✅ Знайдено {len(tasks)} tasks")
            return True
        else:
            print("⚠️ Немає tasks за вчора (це нормально якщо не було запланованих завдань)")
            return True  # Not an error, just no data
            
    except Exception as e:
        print(f"❌ Помилка: {str(e)}")
        return False


def test_4_format_report():
    """Test 4: Тест форматування звіту (без відправки)."""
    print("\n" + "="*60)
    print("Test 4: Report Formatting (Preview)")
    print("="*60)
    
    try:
        manager = DailyReportManager()
        yesterday = datetime.now() - timedelta(days=1)
        tasks = manager._get_tasks_for_date(yesterday)
        
        if not tasks:
            print("⚠️ Немає tasks для форматування")
            return True
        
        platform_reports = manager._group_tasks_by_platform(tasks)
        
        for platform_name, platform_report in platform_reports.items():
            print(f"\n--- Preview for {platform_name.upper()} ---")
            message = manager._format_platform_report(platform_report, yesterday)
            print(message)
            print("--- End Preview ---")
        
        print("\n✅ Форматування працює")
        return True
        
    except Exception as e:
        print(f"❌ Помилка: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_5_send_test_message():
    """Test 5: Відправка тестового повідомлення."""
    print("\n" + "="*60)
    print("Test 5: Send Test Message")
    print("="*60)
    
    try:
        notifier = NotificationManager()
        test_message = "🧪 **Daily Report System Test**\n\nЦе тестове повідомлення від системи щоденних звітів.\n\nЯкщо ви бачите це повідомлення - система працює правильно! ✅"
        
        print("Відправка тестового повідомлення...")
        notifier._send_telegram_message(test_message)
        print("✅ Повідомлення відправлено!")
        print("📱 Перевірте Telegram щоб підтвердити отримання")
        return True
        
    except Exception as e:
        print(f"❌ Помилка: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("Daily Report System - Test Suite")
    print("="*60)
    
    tests = [
        test_1_telegram_connection,
        test_2_database_connection,
        test_3_get_tasks,
        test_4_format_report,
        test_5_send_test_message
    ]
    
    results = []
    
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n❌ Fatal error in {test_func.__name__}: {str(e)}")
            results.append((test_func.__name__, False))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("  1. Run: python run_daily_report.py test")
        print("  2. Start scheduler: python scripts/daily_report_scheduler.py")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

