# ⚡ Task Management - Quick Start

## 🚀 Швидкий старт за 3 кроки

### Крок 1: Створити таблицю в БД

```bash
mysql -u content_fabric_user -p content_fabric < config/mysql_schema.sql
```

### Крок 2: Запустити Task Worker

```python
from app.auto_poster import SocialMediaAutoPoster

poster = SocialMediaAutoPoster(use_database=True)
poster.start_task_worker()
```

### Крок 3: Створити задачу

```bash
python3 run_task_manager.py create \
    --account "Ютуб 6.0" \
    --video "/path/to/video.mp4" \
    --title "Назва відео" \
    --description "Опис відео" \
    --keywords "тег1,тег2,тег3" \
    --schedule "2024-12-25 18:00:00"
```

---

## 📋 Основні команди

```bash
# Список задач
python3 run_task_manager.py list --status pending

# Деталі задачі
python3 run_task_manager.py show 123

# Видалити задачу
python3 run_task_manager.py delete 123

# Статистика
python3 run_task_manager.py stats
```

---

## 🗄️ Створення через SQL

```sql
-- Отримати ID каналу
SELECT id FROM youtube_channels WHERE name = 'Ютуб 6.0';

-- Створити задачу
INSERT INTO tasks 
    (account_id, att_file_path, title, description, keywords, date_post)
VALUES 
    (5, '/var/www/videos/video.mp4', 'Назва', 'Опис', 'теги', '2024-12-25 18:00:00');
```

---

## 📖 Детальна документація

Дивіться [TASK_MANAGEMENT.md](TASK_MANAGEMENT.md) для повної інформації про всі можливості системи.

---

## 🔍 Статуси задач

- **0** - Pending (очікує виконання)
- **1** - Completed (виконано)
- **2** - Failed (помилка)
- **3** - Processing (виконується)

---

## ⚙️ Налаштування

```python
# Змінити інтервал перевірки (в секундах)
worker = TaskWorker(db, check_interval=30)  # кожні 30 секунд

# Змінити кількість спроб
worker = TaskWorker(db, max_retries=5)  # 5 спроб при помилці
```

