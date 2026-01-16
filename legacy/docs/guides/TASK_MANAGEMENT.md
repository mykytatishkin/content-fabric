# 📋 **Руководство по Task Management System**

## 🎯 **Обзор системы**

Task Management System - это механизм автоматической публикации контента на основе задач (тасков) из базы данных MySQL. Система автоматически обрабатывает запланированные задачи, загружает видео на YouTube каналы и отслеживает статус выполнения.

**Основные возможности:**
- ✅ Автоматическое выполнение задач по расписанию
- ✅ Публикация видео на выбранные YouTube каналы
- ✅ Настройка названия, описания и хештегов
- ✅ Автоматические повторы при ошибках
- ✅ CLI для управления задачами
- ✅ Прямая запись в БД или через CLI

---

## 🗄️ **Структура таблицы tasks**

```sql
CREATE TABLE tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,                    -- ID аккаунта из youtube_channels
    media_type VARCHAR(50) DEFAULT 'youtube',   -- Тип медиа (youtube, vk, instagram)
    status TINYINT DEFAULT 0,                   -- 0=pending, 1=completed, 2=failed, 3=processing
    date_add TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    att_file_path TEXT NOT NULL,                -- Путь к видео файлу
    cover TEXT,                                 -- Путь к обложке/thumbnail
    title VARCHAR(500) NOT NULL,                -- Название видео
    description TEXT,                           -- Описание видео
    keywords TEXT,                              -- Ключевые слова/хештеги (через запятую)
    post_comment TEXT,                          -- Комментарий для публикации после загрузки
    add_info JSON,                              -- Дополнительная информация в JSON
    date_post DATETIME NOT NULL,                -- Запланированное время публикации
    date_done DATETIME,                         -- Реальное время выполнения
    error_message TEXT,                         -- Сообщение об ошибке
    retry_count INT DEFAULT 0                   -- Количество попыток повтора
);
```

---

## 🚀 **Быстрый старт**

### **1. Создание таблицы tasks в базе данных**

```bash
# Подключиться к MySQL и выполнить схему
mysql -u content_fabric_user -p content_fabric < config/mysql_schema.sql
```

### **2. Запуск Task Worker (автоматическая обработка)**

```python
# В вашем main.py или отдельном скрипте
from app.auto_poster import SocialMediaAutoPoster

# Инициализация с поддержкой БД
poster = SocialMediaAutoPoster(use_database=True)

# Запуск Task Worker (проверка каждую минуту)
poster.start_task_worker()

# Система работает в фоне
```

### **3. Создание задачи через CLI**

```bash
# Базовая команда
python3 run_task_manager.py create \
    --account "Ютуб 6.0" \
    --video "/path/to/video.mp4" \
    --title "Название видео" \
    --description "Описание видео" \
    --keywords "хештег1,хештег2,хештег3" \
    --schedule "2024-12-25 18:00:00"
```

---

## 📚 **CLI Команды**

### **1. Создание задачи (create)**

Создает новую задачу для публикации видео.

```bash
python3 run_task_manager.py create \
    --account "Имя канала или ID" \
    --video "/path/to/video.mp4" \
    --title "Название видео" \
    [--description "Описание"] \
    [--keywords "tag1,tag2,tag3"] \
    [--cover "/path/to/thumbnail.jpg"] \
    [--comment "Комментарий под видео"] \
    [--schedule "YYYY-MM-DD HH:MM:SS"] \
    [--media-type "youtube"] \
    [--add-info '{"privacy":"public","category":"22"}']
```

**Параметры:**
- `--account` / `-a` - Название канала или ID (обязательно)
- `--video` / `-v` - Путь к видео файлу (обязательно)
- `--title` / `-t` - Название видео (обязательно)
- `--description` / `-d` - Описание видео
- `--keywords` / `-k` - Ключевые слова через запятую
- `--cover` / `-c` - Путь к обложке/thumbnail
- `--comment` - Комментарий для публикации после загрузки
- `--schedule` / `-s` - Время публикации (по умолчанию - сейчас)
- `--media-type` / `-m` - Тип медиа (по умолчанию: youtube)
- `--add-info` - Дополнительная информация в формате JSON

**Пример:**
```bash
python3 run_task_manager.py create \
    --account "Ютуб 6.0" \
    --video "/var/www/videos/my_video.mp4" \
    --title "Как готовить борщ" \
    --description "В этом видео я покажу простой рецепт борща" \
    --keywords "рецепты,борщ,кулинария,готовка" \
    --cover "/var/www/thumbnails/borsch.jpg" \
    --schedule "2024-12-25 18:00:00" \
    --add-info '{"privacy":"public","category":"26"}'
```

**Результат:**
```
✅ Task created successfully!
   Task ID: 123
   Account ID: 5
   Title: Как готовить борщ
   Scheduled for: 2024-12-25 18:00:00
```

---

### **2. Список задач (list)**

Показывает список задач с возможностью фильтрации.

```bash
python3 run_task_manager.py list \
    [--status all|pending|completed|failed|processing] \
    [--limit 50]
```

**Параметры:**
- `--status` - Фильтр по статусу (по умолчанию: all)
  - `all` - Все задачи
  - `pending` - Ожидающие выполнения
  - `completed` - Выполненные
  - `failed` - С ошибками
  - `processing` - В процессе выполнения
- `--limit` / `-l` - Максимальное количество задач (по умолчанию: 50)

**Примеры:**
```bash
# Все задачи
python3 run_task_manager.py list

# Только ожидающие
python3 run_task_manager.py list --status pending

# Последние 10 завершенных
python3 run_task_manager.py list --status completed --limit 10

# Ошибочные задачи
python3 run_task_manager.py list --status failed
```

**Результат:**
```
ID     Account         Type       Status       Title                                    Scheduled           
------------------------------------------------------------------------------------------------------------------------
125    Ютуб 6.0        youtube    Pending      Как готовить борщ                        2024-12-25 18:00    
124    Тесты Канал     youtube    Completed    Обзор техники                            2024-12-24 15:00    
123    Ютуб 6.0        youtube    Failed       Прошлое видео                            2024-12-23 12:00    

Total: 3 task(s)
```

---

### **3. Детали задачи (show)**

Показывает подробную информацию о конкретной задаче.

```bash
python3 run_task_manager.py show <task_id>
```

**Пример:**
```bash
python3 run_task_manager.py show 125
```

**Результат:**
```
============================================================
Task #125 Details
============================================================
Account:        Ютуб 6.0 (ID: 5)
Media Type:     youtube
Status:         Pending
Title:          Как готовить борщ
Description:    В этом видео я покажу простой рецепт борща
Keywords:       рецепты,борщ,кулинария,готовка
Video Path:     /var/www/videos/my_video.mp4
Cover:          /var/www/thumbnails/borsch.jpg
Comment:        N/A
Additional:     {"privacy":"public","category":"26"}
Scheduled:      2024-12-25 18:00:00
Created:        2024-12-24 10:30:15
Completed:      N/A
Retry Count:    0
============================================================
```

---

### **4. Удаление задачи (delete)**

Удаляет задачу из базы данных.

```bash
python3 run_task_manager.py delete <task_id> [--force]
```

**Параметры:**
- `task_id` - ID задачи для удаления
- `--force` / `-f` - Пропустить подтверждение

**Примеры:**
```bash
# С подтверждением
python3 run_task_manager.py delete 125

# Без подтверждения
python3 run_task_manager.py delete 125 --force
```

**Результат:**
```
Are you sure you want to delete task #125? (y/N): y
✅ Task #125 deleted successfully
```

---

### **5. Статистика (stats)**

Показывает общую статистику по задачам и каналам.

```bash
python3 run_task_manager.py stats
```

**Результат:**
```
============================================================
Task Statistics
============================================================
Total Tasks:     150
Pending:         12
Completed:       130
Failed:          8
============================================================
Total Channels:  5
Enabled:         4
============================================================
```

---

## 🔧 **Прямая работа с базой данных**

### **Создание задачи через SQL**

```sql
INSERT INTO tasks 
    (account_id, media_type, att_file_path, title, description, 
     keywords, date_post, cover, post_comment, add_info)
VALUES 
    (5, 'youtube', '/var/www/videos/video.mp4', 'Название видео', 
     'Описание видео', 'tag1,tag2,tag3', '2024-12-25 18:00:00', 
     '/var/www/thumbnails/cover.jpg', 'Комментарий', 
     '{"privacy":"public","category":"26"}');
```

### **Получение ID канала по имени**

```sql
SELECT id, name FROM youtube_channels WHERE name = 'Ютуб 6.0';
```

### **Просмотр pending задач**

```sql
SELECT id, title, date_post, status 
FROM tasks 
WHERE status = 0 AND date_post <= NOW()
ORDER BY date_post ASC;
```

### **Изменение статуса задачи**

```sql
-- Отметить как выполненную
UPDATE tasks SET status = 1, date_done = NOW() WHERE id = 125;

-- Сбросить на pending для повтора
UPDATE tasks SET status = 0, retry_count = retry_count + 1 WHERE id = 125;
```

---

## 🤖 **Программное использование (Python)**

### **Инициализация Task Worker**

```python
from app.auto_poster import SocialMediaAutoPoster

# Создать auto-poster с поддержкой БД
poster = SocialMediaAutoPoster(
    config_path="config/config.yaml",
    use_database=True
)

# Запустить Task Worker
poster.start_task_worker()

# Получить статистику
stats = poster.get_task_worker_stats()
print(stats)

# Остановить Worker
poster.stop_task_worker()
```

### **Работа с базой данных напрямую**

```python
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime

# Подключиться к БД
db = YouTubeMySQLDatabase()

# Создать задачу
task_id = db.create_task(
    account_id=5,
    att_file_path="/var/www/videos/video.mp4",
    title="Название видео",
    date_post=datetime(2024, 12, 25, 18, 0, 0),
    description="Описание",
    keywords="tag1,tag2,tag3",
    cover="/var/www/thumbnails/cover.jpg",
    add_info={"privacy": "public", "category": "26"}
)

# Получить pending задачи
pending_tasks = db.get_pending_tasks(limit=10)
for task in pending_tasks:
    print(f"Task #{task.id}: {task.title}")

# Получить задачу по ID
task = db.get_task(task_id)
print(f"Status: {task.status}")

# Обновить статус
db.mark_task_completed(task_id)
# или
db.mark_task_failed(task_id, "Ошибка загрузки")

# Закрыть соединение
db.close()
```

### **Ручная обработка одной задачи**

```python
from app.task_worker import TaskWorker
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()
worker = TaskWorker(db)

# Обработать конкретную задачу
success = worker.process_single_task(task_id=125)
if success:
    print("✅ Task processed successfully")
else:
    print("❌ Task processing failed")
```

---

## ⚙️ **Настройка Task Worker**

### **Параметры при инициализации**

```python
from app.task_worker import TaskWorker

worker = TaskWorker(
    db=mysql_db,
    check_interval=60,  # Проверка каждые 60 секунд (1 минута)
    max_retries=3,      # Максимум 3 попытки при ошибке
    auto_cleanup=True   # Автоматически удалять файлы после публикации
)
```

### **Изменение интервала проверки**

Чтобы изменить интервал проверки с 1 минуты на другой:

```python
# В app/auto_poster.py, строка 62
self.task_worker = TaskWorker(
    self.mysql_db, 
    check_interval=30,  # Проверка каждые 30 секунд
    max_retries=5,      # 5 попыток
    auto_cleanup=True   # True = удалять файлы, False = сохранять
)
```

### **🗑️ Автоматическое удаление файлов**

**По умолчанию ВКЛЮЧЕНО** - после успешной публикации Worker автоматически удаляет:
- ✅ Видео файл (`att_file_path`)
- ✅ Обложку (`cover`)

**Зачем это нужно:**
- 💾 Экономия места на сервере
- 🧹 Автоматическая очистка после публикации
- ⏱️ Не нужно вручную удалять файлы

**Что происходит при успешной публикации:**
```
✅ Task #123 completed successfully. Video ID: abc123
🗑️  Deleted video file: /var/www/videos/video.mp4 (245.67 MB)
🗑️  Deleted cover file: /var/www/thumbnails/cover.jpg (128.45 KB)
✅ Cleanup complete for task #123. Deleted: Video, Cover
```

**Чтобы ОТКЛЮЧИТЬ автоудаление:**
```python
# В app/auto_poster.py, строка 66
self.task_worker = TaskWorker(
    self.mysql_db, 
    check_interval=60, 
    max_retries=3,
    auto_cleanup=False  # Файлы НЕ будут удаляться
)
```

**Важные моменты:**
- ✅ Файлы удаляются **ТОЛЬКО** после успешной публикации (`status = 1`)
- ✅ Если публикация провалилась - файлы **сохраняются** для повторных попыток
- ✅ Если файла нет (уже удален вручную) - Worker просто предупреждает, но продолжает работу
- ✅ В логах показывается размер удаленных файлов
- ⚠️ После удаления восстановить файлы **невозможно**!

**Проверка настройки:**
```bash
python3 run_task_worker.py
```
Вы увидите:
```
✅ Task Worker запущено успішно
   Інтервал перевірки: 60 секунд
   Максимум спроб: 3
   Автовидалення файлів: ✅ Увімкнено  # або ❌ Вимкнено
```

---

## 📊 **Мониторинг и статус**

### **Проверка статуса системы**

```python
from app.auto_poster import SocialMediaAutoPoster

poster = SocialMediaAutoPoster(use_database=True)
poster.start_task_worker()

# Получить полный статус системы
status = poster.get_system_status()

print("Task Worker Status:")
print(f"  Running: {status['task_worker']['running']}")
print(f"  Total Processed: {status['task_worker']['statistics']['total_processed']}")
print(f"  Successful: {status['task_worker']['statistics']['successful']}")
print(f"  Failed: {status['task_worker']['statistics']['failed']}")

print("\nDatabase Stats:")
print(f"  Total Tasks: {status['database_stats']['total_tasks']}")
print(f"  Pending: {status['database_stats']['pending_tasks']}")
print(f"  Completed: {status['database_stats']['completed_tasks']}")
```

### **Просмотр логов**

```bash
# Логи Task Worker
tail -f data/logs/auto_posting.log | grep task_worker
```

---

## 🎯 **Примеры использования**

### **Пример 1: Публикация одного видео на один канал**

```bash
# Создать задачу на публикацию через 2 часа
python3 run_task_manager.py create \
    --account "Ютуб 6.0" \
    --video "/var/www/videos/cooking_tutorial.mp4" \
    --title "Готовим пиццу дома" \
    --description "Простой рецепт домашней пиццы" \
    --keywords "пицца,рецепты,кулинария" \
    --cover "/var/www/thumbnails/pizza.jpg" \
    --schedule "2024-12-25 20:00:00"
```

### **Пример 2: Массовая загрузка через SQL**

```sql
-- Подготовить несколько видео для разных каналов
INSERT INTO tasks (account_id, att_file_path, title, description, keywords, date_post) VALUES
(5, '/var/www/videos/video1.mp4', 'Видео 1', 'Описание 1', 'tag1', '2024-12-25 09:00:00'),
(5, '/var/www/videos/video2.mp4', 'Видео 2', 'Описание 2', 'tag2', '2024-12-25 12:00:00'),
(6, '/var/www/videos/video3.mp4', 'Видео 3', 'Описание 3', 'tag3', '2024-12-25 15:00:00'),
(6, '/var/www/videos/video4.mp4', 'Видео 4', 'Описание 4', 'tag4', '2024-12-25 18:00:00');
```

### **Пример 3: Автоматический скрипт создания задач**

```python
#!/usr/bin/env python3
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime, timedelta
from pathlib import Path

db = YouTubeMySQLDatabase()

# Список видео для публикации
videos = [
    {
        "path": "/var/www/videos/video1.mp4",
        "title": "Видео 1",
        "description": "Описание 1",
        "keywords": "tag1,tag2",
        "channel": "Ютуб 6.0"
    },
    {
        "path": "/var/www/videos/video2.mp4",
        "title": "Видео 2",
        "description": "Описание 2",
        "keywords": "tag3,tag4",
        "channel": "Тесты Канал"
    }
]

# Создать задачи с интервалом 3 часа
start_time = datetime.now() + timedelta(hours=1)

for i, video in enumerate(videos):
    # Получить ID канала
    channel = db.get_channel(video["channel"])
    if not channel:
        print(f"❌ Канал {video['channel']} не найден")
        continue
    
    # Время публикации
    publish_time = start_time + timedelta(hours=i * 3)
    
    # Создать задачу
    task_id = db.create_task(
        account_id=channel.id,
        att_file_path=video["path"],
        title=video["title"],
        description=video["description"],
        keywords=video["keywords"],
        date_post=publish_time
    )
    
    print(f"✅ Task {task_id} created for {video['channel']} at {publish_time}")

db.close()
```

---

## 🔍 **Troubleshooting**

### **Проблема: Задачи не выполняются автоматически**

**Решение:**
1. Проверьте, запущен ли Task Worker:
```python
status = poster.get_task_worker_stats()
print(status['running'])  # Должно быть True
```

2. Проверьте время в задаче:
```bash
python3 run_task_manager.py show <task_id>
# Убедитесь что date_post <= текущему времени
```

3. Проверьте статус задачи:
```sql
SELECT id, title, status, date_post FROM tasks WHERE id = <task_id>;
-- status должен быть 0 (pending)
```

### **Проблема: Задача завершается с ошибкой**

**Решение:**
1. Посмотрите детали ошибки:
```bash
python3 run_task_manager.py show <task_id>
# Проверьте поле Error
```

2. Проверьте существование файла:
```bash
ls -la /path/to/video.mp4
```

3. Проверьте токены канала:
```sql
SELECT name, access_token, token_expires_at, enabled 
FROM youtube_channels 
WHERE id = <account_id>;
```

4. Проверьте логи:
```bash
tail -f data/logs/auto_posting.log
```

### **Проблема: "Channel not found"**

**Решение:**
1. Проверьте список каналов:
```bash
python3 run_youtube_manager.py list
```

2. Используйте правильное имя или ID:
```bash
# По имени
python3 run_task_manager.py create --account "Ютуб 6.0" ...

# По ID
python3 run_task_manager.py create --account "5" ...
```

### **Проблема: "Video file not found"**

**Решение:**
1. Используйте абсолютный путь:
```bash
python3 run_task_manager.py create \
    --video "/var/www/fastuser/data/www/aiyoutube.pbnbots.com/data/video.mp4" \
    ...
```

2. Проверьте права доступа:
```bash
ls -la /path/to/video.mp4
chmod 644 /path/to/video.mp4
```

---

## 📖 **Дополнительные ресурсы**

- [YouTube Setup Guide](YOUTUBE_SETUP.md) - Настройка YouTube API
- [Channel Management](CHANNEL_MANAGEMENT.md) - Управление каналами
- [MySQL Setup](../setup/MYSQL_SETUP_GUIDE.md) - Настройка базы данных

---

## 💡 **Tips & Tricks**

### **1. Быстрая проверка pending задач**

```bash
# Сколько задач ждут выполнения
python3 run_task_manager.py list --status pending | tail -1
```

### **2. Просмотр failed задач для анализа**

```bash
python3 run_task_manager.py list --status failed --limit 100 > failed_tasks.txt
```

### **3. Массовое создание задач из CSV**

```python
import csv
from core.database.mysql_db import YouTubeMySQLDatabase
from datetime import datetime

db = YouTubeMySQLDatabase()

with open('tasks.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        db.create_task(
            account_id=int(row['account_id']),
            att_file_path=row['video_path'],
            title=row['title'],
            description=row['description'],
            keywords=row['keywords'],
            date_post=datetime.fromisoformat(row['schedule'])
        )

db.close()
```

### **4. Мониторинг в реальном времени**

```bash
# Следить за статусом задач
watch -n 5 'python3 run_task_manager.py stats'
```

---

**Создано**: 2024  
**Версия**: 1.0  
**Проект**: Content Fabric Task Management System

