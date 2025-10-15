#!/usr/bin/env python3
"""
Daily Report Example - Приклади використання системи щоденних звітів.

Цей файл демонструє різні способи роботи з Daily Report Manager.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.utils.daily_report import DailyReportManager, send_daily_report
from core.database.mysql_db import YouTubeMySQLDatabase
from core.utils.notifications import NotificationManager


def example_1_basic_usage():
    """Приклад 1: Базове використання - звіт за вчора."""
    print("=" * 60)
    print("Приклад 1: Базовий звіт за вчора")
    print("=" * 60)
    
    manager = DailyReportManager()
    success = manager.generate_and_send_daily_report()
    
    if success:
        print("✅ Звіт успішно відправлено!")
    else:
        print("❌ Помилка при відправці звіту")


def example_2_specific_date():
    """Приклад 2: Звіт за конкретну дату."""
    print("\n" + "=" * 60)
    print("Приклад 2: Звіт за конкретну дату")
    print("=" * 60)
    
    # Звіт за 3 дні тому
    target_date = datetime.now() - timedelta(days=3)
    print(f"Генеруємо звіт за {target_date.strftime('%Y-%m-%d')}")
    
    manager = DailyReportManager()
    success = manager.generate_and_send_daily_report(date=target_date)
    
    if success:
        print("✅ Звіт успішно відправлено!")
    else:
        print("❌ Помилка при відправці звіту")


def example_3_custom_components():
    """Приклад 3: Використання власних компонентів."""
    print("\n" + "=" * 60)
    print("Приклад 3: Власні компоненти DB та Notifier")
    print("=" * 60)
    
    # Створити власні інстанси
    db = YouTubeMySQLDatabase()
    notifier = NotificationManager()
    
    # Використати їх в DailyReportManager
    manager = DailyReportManager(db=db, notification_manager=notifier)
    
    success = manager.generate_and_send_daily_report()
    
    if success:
        print("✅ Звіт з власними компонентами відправлено!")
    else:
        print("❌ Помилка при відправці")


def example_4_standalone_function():
    """Приклад 4: Використання standalone функції (для cron)."""
    print("\n" + "=" * 60)
    print("Приклад 4: Standalone функція для cron")
    print("=" * 60)
    
    # Проста функція без параметрів - ідеальна для cron
    success = send_daily_report()
    
    if success:
        print("✅ Cron job виконано успішно!")
    else:
        print("❌ Cron job завершився з помилкою")


def example_5_test_report():
    """Приклад 5: Тестовий звіт."""
    print("\n" + "=" * 60)
    print("Приклад 5: Тестовий звіт")
    print("=" * 60)
    
    manager = DailyReportManager()
    success = manager.send_test_report()
    
    if success:
        print("✅ Тестовий звіт відправлено!")
    else:
        print("❌ Помилка при відправці тестового звіту")


def example_6_get_tasks_info():
    """Приклад 6: Отримання інформації про tasks без відправки."""
    print("\n" + "=" * 60)
    print("Приклад 6: Перегляд tasks без відправки")
    print("=" * 60)
    
    manager = DailyReportManager()
    yesterday = datetime.now() - timedelta(days=1)
    
    # Отримати tasks
    tasks = manager._get_tasks_for_date(yesterday)
    
    print(f"\nТasks за {yesterday.strftime('%Y-%m-%d')}:")
    print(f"Всього: {len(tasks)}")
    
    if tasks:
        # Групувати по статусах
        status_map = {0: 'Pending', 1: 'Completed', 2: 'Failed', 3: 'Processing'}
        status_counts = {}
        
        for task in tasks:
            status_name = status_map.get(task.status, 'Unknown')
            status_counts[status_name] = status_counts.get(status_name, 0) + 1
        
        print("\nПо статусах:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
    else:
        print("  Немає tasks за цей день")


def example_7_format_report_preview():
    """Приклад 7: Попередній перегляд звіту без відправки."""
    print("\n" + "=" * 60)
    print("Приклад 7: Попередній перегляд звіту")
    print("=" * 60)
    
    manager = DailyReportManager()
    yesterday = datetime.now() - timedelta(days=1)
    
    # Отримати tasks та згрупувати
    tasks = manager._get_tasks_for_date(yesterday)
    
    if not tasks:
        print("Немає tasks для попереднього перегляду")
        return
    
    platform_reports = manager._group_tasks_by_platform(tasks)
    
    # Показати попередній перегляд кожної платформи
    for platform_name, platform_report in platform_reports.items():
        message = manager._format_platform_report(platform_report, yesterday)
        print(f"\n--- Попередній перегляд для {platform_name.upper()} ---")
        print(message)
        print("--- Кінець попереднього перегляду ---")


def main():
    """Головна функція з меню прикладів."""
    print("\n" + "="*60)
    print("Daily Report Manager - Приклади використання")
    print("="*60)
    
    examples = {
        '1': ('Базовий звіт за вчора', example_1_basic_usage),
        '2': ('Звіт за конкретну дату', example_2_specific_date),
        '3': ('Власні компоненти', example_3_custom_components),
        '4': ('Standalone функція (cron)', example_4_standalone_function),
        '5': ('Тестовий звіт', example_5_test_report),
        '6': ('Перегляд tasks', example_6_get_tasks_info),
        '7': ('Попередній перегляд звіту', example_7_format_report_preview),
        'all': ('Запустити всі приклади', None)
    }
    
    print("\nДоступні приклади:")
    for key, (description, _) in examples.items():
        print(f"  {key}. {description}")
    
    # Якщо аргумент командного рядка
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nОберіть приклад (або 'all' для всіх): ").strip()
    
    if choice == 'all':
        for key, (description, func) in examples.items():
            if func:  # Пропустити 'all'
                try:
                    func()
                except Exception as e:
                    print(f"❌ Помилка в прикладі {key}: {str(e)}")
    elif choice in examples:
        description, func = examples[choice]
        if func:
            try:
                func()
            except Exception as e:
                print(f"❌ Помилка: {str(e)}")
        else:
            print("Неправильний вибір")
    else:
        print("Невідомий приклад. Використайте номер з меню.")
    
    print("\n" + "="*60)
    print("Завершено!")
    print("="*60)


if __name__ == "__main__":
    main()

