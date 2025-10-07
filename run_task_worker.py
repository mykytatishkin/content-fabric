#!/usr/bin/env python3
"""
Task Worker Runner - Запускає Task Worker для автоматичної обробки задач з БД.

Використання:
    python3 run_task_worker.py
    
Або в фоновому режимі:
    nohup python3 run_task_worker.py > task_worker.log 2>&1 &
"""

import sys
import signal
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.auto_poster import SocialMediaAutoPoster


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n⚠️  Отримано сигнал зупинки...")
    if poster and poster.task_worker:
        poster.stop_task_worker()
    print("✅ Task Worker зупинено")
    sys.exit(0)


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Task Worker - Automatic Task Processing")
    print("=" * 60)
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize auto-poster with database support
        print("📦 Ініціалізація системи...")
        poster = SocialMediaAutoPoster(
            config_path="config/config.yaml",
            use_database=True
        )
        
        if not poster.task_worker:
            print("❌ Task Worker не вдалося ініціалізувати")
            print("   Перевірте налаштування MySQL в config/mysql_config.yaml")
            sys.exit(1)
        
        # Start task worker
        print("▶️  Запуск Task Worker...")
        poster.start_task_worker()
        
        # Get worker configuration
        stats = poster.get_task_worker_stats()
        print(f"✅ Task Worker запущено успішно")
        print(f"   Інтервал перевірки: {stats['check_interval']} секунд")
        print(f"   Максимум спроб: {stats['max_retries']}")
        print("\n💡 Для зупинки натисніть Ctrl+C")
        print("=" * 60)
        
        # Keep the main thread alive
        while True:
            time.sleep(10)
            
            # Periodically print stats
            stats = poster.get_task_worker_stats()
            if stats['statistics']['total_processed'] > 0:
                print(f"\r📊 Оброблено: {stats['statistics']['total_processed']} | "
                      f"Успішно: {stats['statistics']['successful']} | "
                      f"Помилки: {stats['statistics']['failed']} | "
                      f"Повтори: {stats['statistics']['retried']}", end='', flush=True)
        
    except KeyboardInterrupt:
        print("\n⚠️  Отримано сигнал зупинки...")
        if poster and poster.task_worker:
            poster.stop_task_worker()
        print("✅ Task Worker зупинено")
        
    except Exception as e:
        print(f"\n❌ Критична помилка: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

