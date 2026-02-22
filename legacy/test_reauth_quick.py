#!/usr/bin/env python3
"""Quick test script - можно запустить прямо в терминале"""
from core.database.mysql_db import get_mysql_database
from app.task_worker import TaskWorker

# 1. Найти канал с отозванным токеном
db = get_mysql_database()
channel_name = "Readbooks-online"  # Замените на ваш канал
channel = db.get_channel(channel_name)

if not channel:
    print(f"❌ Канал '{channel_name}' не найден")
    exit(1)

print(f"✅ Канал найден: {channel.name}")

# 2. Найти pending задачу
pending_tasks = db.get_pending_tasks()
task = None
for t in pending_tasks:
    if t.channel_id == channel.id:
        task = t
        break

if not task:
    print(f"⚠️  Нет pending задач для канала {channel_name}")
    print("   Создайте задачу в БД или используйте существующую")
    exit(1)

print(f"✅ Найдена задача #{task.id}: {task.title}")

# 3. Обработать задачу
print("\n🔄 Обрабатываю задачу...")
worker = TaskWorker(db=db)
result = worker.process_single_task(task.id)

print(f"\n📊 Результат: {'✅ Успешно' if result else '❌ Ошибка'}")

# 4. Проверить переавторизацию
import time
time.sleep(2)  # Подождать запуска фонового потока

if channel_name in worker.ongoing_reauths:
    print(f"✅ Переавторизация запущена для {channel_name}")
else:
    print(f"ℹ️  Переавторизация не запущена")
    print("   (Возможно, токен валиден или ошибка не связана с токеном)")

print("\n📱 Проверьте Telegram - должны прийти уведомления!")
