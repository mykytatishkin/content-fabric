#!/usr/bin/env python3
"""
Проверка почему автоматическая переавторизация не работает.
Анализирует ошибки в задачах и проверяет, должны ли они были вызвать переавторизацию.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from core.database.mysql_db import get_mysql_database
from core.utils.error_categorizer import ErrorCategorizer
from core.utils.logger import get_logger

logger = get_logger("check_reauth")


def check_reauth_logic():
    """Проверить логику автоматической переавторизации."""
    print("=" * 80)
    print("🔍 ПРОВЕРКА АВТОМАТИЧЕСКОЙ ПЕРЕАВТОРИЗАЦИИ")
    print("=" * 80)
    print()
    
    db = get_mysql_database()
    if not db:
        print("❌ Не удалось подключиться к базе данных")
        return 1
    
    # Получить провалившиеся задачи за последние 7 дней
    yesterday = datetime.now() - timedelta(days=1)
    week_ago = datetime.now() - timedelta(days=7)
    
    query = """
        SELECT t.id, t.channel_id, t.status, t.error_message, t.scheduled_at,
               c.name as channel_name
        FROM content_upload_queue_tasks t
        JOIN platform_channels c ON t.channel_id = c.id
        WHERE t.status = 2
          AND t.scheduled_at >= %s
          AND t.scheduled_at <= %s
        ORDER BY t.scheduled_at DESC
        LIMIT 100
    """
    
    failed_tasks = db._execute_query(query, (week_ago, yesterday), fetch=True)
    
    if not failed_tasks:
        print("✅ Нет провалившихся задач за последние 7 дней")
        return 0
    
    print(f"📊 Найдено {len(failed_tasks)} провалившихся задач\n")
    
    # Анализ ошибок
    auth_errors = []
    should_trigger_reauth = []
    other_errors = []
    
    for task in failed_tasks:
        task_id = task[0]
        channel_name = task[5] if len(task) > 5 else f"ID-{task[1]}"
        error_msg = task[3] if task[3] else "No error message"
        
        # Категоризировать ошибку
        error_category = ErrorCategorizer.categorize(error_msg)
        
        # Проверить, должна ли эта ошибка вызвать переавторизацию
        # (логика из task_worker.py)
        is_refresh_token_invalid = (
            error_category == 'Auth' and 
            ('invalid_grant' in error_msg.lower() or 
             'token has been expired or revoked' in error_msg.lower() or
             'refresh token' in error_msg.lower() and 'invalid' in error_msg.lower() or
             'refresh token' in error_msg.lower() and 'revoked' in error_msg.lower() or
             'failed to refresh token' in error_msg.lower())
        )
        
        if error_category == 'Auth':
            auth_errors.append({
                'task_id': task_id,
                'channel': channel_name,
                'error': error_msg[:150],
                'should_reauth': is_refresh_token_invalid
            })
            
            if is_refresh_token_invalid:
                should_trigger_reauth.append({
                    'task_id': task_id,
                    'channel': channel_name,
                    'error': error_msg[:150]
                })
        else:
            other_errors.append({
                'task_id': task_id,
                'channel': channel_name,
                'category': error_category,
                'error': error_msg[:150]
            })
    
    # Вывод результатов
    print("=" * 80)
    print("📋 АНАЛИЗ ОШИБОК")
    print("=" * 80)
    print()
    
    print(f"🔐 Ошибки аутентификации (Auth): {len(auth_errors)}")
    print(f"   ⚠️  Должны были вызвать переавторизацию: {len(should_trigger_reauth)}")
    print(f"   ❌ Другие Auth ошибки: {len(auth_errors) - len(should_trigger_reauth)}")
    print(f"📦 Другие ошибки: {len(other_errors)}")
    print()
    
    if should_trigger_reauth:
        print("=" * 80)
        print("⚠️  ЗАДАЧИ, КОТОРЫЕ ДОЛЖНЫ БЫЛИ ВЫЗВАТЬ ПЕРЕАВТОРИЗАЦИЮ")
        print("=" * 80)
        print()
        
        # Группировать по каналам
        channels_needing_reauth = {}
        for item in should_trigger_reauth:
            channel = item['channel']
            if channel not in channels_needing_reauth:
                channels_needing_reauth[channel] = []
            channels_needing_reauth[channel].append(item)
        
        for channel, items in sorted(channels_needing_reauth.items()):
            print(f"📺 {channel} ({len(items)} задач)")
            for item in items[:3]:  # Показать первые 3
                print(f"   Task #{item['task_id']}: {item['error']}")
            if len(items) > 3:
                print(f"   ... и еще {len(items) - 3} задач")
            print()
        
        # Проверить, была ли переавторизация
        print("=" * 80)
        print("🔍 ПРОВЕРКА: БЫЛА ЛИ ПЕРЕАВТОРИЗАЦИЯ?")
        print("=" * 80)
        print()
        
        # Проверить таблицу reauth_audit
        try:
            reauth_query = """
                SELECT c.name, a.status, a.created_at, a.error_message
                FROM channel_reauth_audit_logs a
                JOIN platform_channels c ON a.channel_id = c.id
                WHERE c.name IN (%s)
                ORDER BY a.created_at DESC
                LIMIT 50
            """
            
            channel_names = list(channels_needing_reauth.keys())
            if channel_names:
                placeholders = ','.join(['%s'] * len(channel_names))
                reauth_query = reauth_query.replace('%s', placeholders)
                reauth_results = db._execute_query(reauth_query, tuple(channel_names), fetch=True)
                
                if reauth_results:
                    print(f"✅ Найдено {len(reauth_results)} записей о переавторизации:")
                    print()
                    for record in reauth_results[:10]:
                        status = record[1]
                        date_add = record[2]
                        error = record[3] if len(record) > 3 else None
                        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⏳"
                        print(f"   {status_icon} {record[0]} - {status} ({date_add})")
                        if error:
                            print(f"      Error: {error[:100]}")
                else:
                    print("❌ НЕТ записей о переавторизации для этих каналов!")
                    print("   Это означает, что автоматическая переавторизация НЕ запускалась")
        except Exception as e:
            print(f"⚠️  Не удалось проверить таблицу reauth_audit: {e}")
            print("   (Возможно, таблица не существует или структура отличается)")
        
        print()
        print("=" * 80)
        print("💡 ВОЗМОЖНЫЕ ПРИЧИНЫ")
        print("=" * 80)
        print()
        print("1. Task Worker НЕ был запущен во время обработки этих задач")
        print("2. Ошибки произошли ДО того, как код переавторизации был добавлен")
        print("3. Ошибка в логике определения invalid_grant (проверьте точный текст ошибки)")
        print("4. Переавторизация запустилась, но упала с ошибкой (проверьте логи)")
        print()
        print("🔧 РЕКОМЕНДАЦИИ:")
        print()
        print("1. Проверьте логи task_worker:")
        print("   tail -100 data/logs/task_worker.log | grep -i 'reauth\\|token\\|revocation'")
        print()
        print("2. Проверьте, запущен ли task_worker сейчас:")
        print("   ps aux | grep run_task_worker")
        print()
        print("3. Попробуйте обработать одну из этих задач вручную:")
        print("   python3 -c \"")
        print("   from core.database.mysql_db import get_mysql_database")
        print("   from app.task_worker import TaskWorker")
        print("   db = get_mysql_database()")
        print("   worker = TaskWorker(db=db)")
        print("   task = db.get_task(TASK_ID)  # Замените на реальный ID")
        print("   channel = db.get_channel('CHANNEL_NAME')  # Замените на реальное имя")
        print("   worker._process_youtube_task(task, channel)")
        print("   \"")
    
    if auth_errors and not should_trigger_reauth:
        print("=" * 80)
        print("⚠️  ОШИБКИ АУТЕНТИФИКАЦИИ НЕ РАСПОЗНАНЫ КАК invalid_grant")
        print("=" * 80)
        print()
        print("Ошибки Auth найдены, но они не соответствуют паттернам для переавторизации:")
        print()
        for item in auth_errors[:10]:
            print(f"   Task #{item['task_id']} ({item['channel']}):")
            print(f"   {item['error']}")
            print()
        print("💡 Проверьте, что ошибки содержат:")
        print("   - 'invalid_grant'")
        print("   - 'Token has been expired or revoked'")
        print("   - 'refresh token' + 'invalid' или 'revoked'")
        print("   - 'failed to refresh token'")
    
    if other_errors:
        print("=" * 80)
        print("📦 ДРУГИЕ ОШИБКИ (не Auth)")
        print("=" * 80)
        print()
        categories = {}
        for item in other_errors:
            cat = item['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        for category, items in sorted(categories.items()):
            print(f"   {category}: {len(items)} задач")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(check_reauth_logic())
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(1)
    except Exception as e:
        logger.exception("Ошибка при проверке: %s", e)
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
