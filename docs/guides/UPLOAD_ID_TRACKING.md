# 📹 Отслеживание Upload ID видео

## 🎯 Описание

После успешной загрузки видео, система автоматически сохраняет ID видео (upload_id) в таблицу `tasks`. Это позволяет отслеживать, какой ID получило каждое загруженное видео на платформе.

---

## 🔄 Как работает автоматическое заполнение

### Шаг 1: Task Worker обрабатывает задачу
```python
# app/task_worker.py (строка 214-226)

result = self.youtube_client.post_video(
    account_info=account_info,
    video_path=task.att_file_path,
    caption=task.description or '',
    metadata={...}
)
```

### Шаг 2: YouTube API возвращает ID видео
```python
# core/api_clients/youtube_client.py (строка 298-302)

if response:
    video_id = response['id']  # Например: "dQw4w9WgXcQ"
    return PostResult(
        success=True,
        post_id=video_id,  # ← Этот ID будет сохранен
        platform="YouTube",
        account=account_name
    )
```

### Шаг 3: Task Worker сохраняет upload_id в БД
```python
# app/task_worker.py (строка 228-231)

if result.success:
    self.logger.info(f"Task #{task.id} completed successfully. Video ID: {result.post_id}")
    # ✅ Автоматически сохраняем upload_id
    self.db.mark_task_completed(task.id, upload_id=result.post_id)
```

### Шаг 4: SQL запрос обновляет таблицу
```sql
-- core/database/mysql_db.py (строка 468-472)

UPDATE tasks 
SET status = 1, 
    date_done = NOW(), 
    upload_id = 'dQw4w9WgXcQ'  -- ID видео с YouTube
WHERE id = 123;
```

---

## 📊 Пример в базе данных

После успешной загрузки видео запись в таблице `tasks` будет выглядеть так:

```sql
SELECT id, title, status, upload_id, date_done 
FROM tasks 
WHERE id = 123;
```

**Результат:**
```
+-----+------------------------+--------+-------------+---------------------+
| id  | title                  | status | upload_id   | date_done           |
+-----+------------------------+--------+-------------+---------------------+
| 123 | Мое крутое видео       | 1      | dQw4w9WgXcQ | 2024-10-10 11:45:32 |
+-----+------------------------+--------+-------------+---------------------+
```

Где:
- `status = 1` означает "completed" (успешно завершено)
- `upload_id = 'dQw4w9WgXcQ'` - ID видео на YouTube
- `date_done` - реальное время завершения загрузки

---

## 🔍 Как использовать upload_id

### 1. Получить прямую ссылку на видео
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()
task = db.get_task(task_id=123)

if task.upload_id:
    video_url = f"https://www.youtube.com/watch?v={task.upload_id}"
    print(f"Видео доступно по адресу: {video_url}")
```

### 2. Найти все загруженные видео
```sql
-- Получить все успешно загруженные задачи
SELECT id, title, upload_id, date_done 
FROM tasks 
WHERE status = 1 
  AND upload_id IS NOT NULL
ORDER BY date_done DESC;
```

### 3. Статистика по загрузкам
```sql
-- Посчитать количество успешных загрузок
SELECT 
    COUNT(*) as total_uploads,
    COUNT(upload_id) as with_video_id,
    DATE(date_done) as upload_date
FROM tasks 
WHERE status = 1
GROUP BY DATE(date_done)
ORDER BY upload_date DESC;
```

### 4. Проверить загрузку конкретной задачи
```python
task = db.get_task(task_id=123)

if task.status == 1 and task.upload_id:
    print(f"✅ Видео успешно загружено!")
    print(f"   Video ID: {task.upload_id}")
    print(f"   URL: https://www.youtube.com/watch?v={task.upload_id}")
elif task.status == 0:
    print("⏳ Задача ожидает выполнения")
elif task.status == 2:
    print("❌ Задача не выполнена (ошибка)")
elif task.status == 3:
    print("⚙️  Задача выполняется...")
```

---

## 🎬 Полный процесс работы

```
1. Создание задачи
   ↓
2. Task Worker получает задачу (status=0)
   ↓
3. Устанавливает status=3 (processing)
   ↓
4. Загружает видео на YouTube
   ↓
5. YouTube API возвращает video_id (например: "dQw4w9WgXcQ")
   ↓
6. Task Worker обновляет запись:
   - status = 1 (completed)
   - upload_id = "dQw4w9WgXcQ" ← Сохраняется автоматически!
   - date_done = текущее время
   ↓
7. ✅ Готово! ID видео сохранен в БД
```

---

## 📝 Дополнительные методы

### Обновить upload_id вручную (если нужно)
```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Обновить только upload_id без изменения статуса
db.update_task_upload_id(task_id=123, upload_id="новый_video_id")
```

### Получить все задачи с video ID
```python
# Получить все завершенные задачи
completed_tasks = db.get_all_tasks(status=1)

for task in completed_tasks:
    if task.upload_id:
        print(f"Task #{task.id}: {task.title}")
        print(f"  Video ID: {task.upload_id}")
        print(f"  URL: https://www.youtube.com/watch?v={task.upload_id}")
        print()
```

---

## 🛠️ Миграция для существующих баз данных

Если у вас уже есть таблица `tasks`, выполните миграцию:

```bash
python3 run_migration_upload_id.py
```

Миграция:
- ✅ Добавит колонку `upload_id VARCHAR(255)`
- ✅ Создаст индекс для быстрого поиска
- ✅ Безопасна для повторного запуска
- ✅ Не удаляет существующие данные

---

## 📌 Итого

**Что добавлено:**
- Поле `upload_id` в таблице `tasks`
- Автоматическое сохранение video ID после загрузки
- Индекс для быстрого поиска по video ID
- Метод `update_task_upload_id()` для ручного обновления

**Когда заполняется:**
- ✅ Автоматически при успешной загрузке видео через Task Worker
- ✅ Можно обновить вручную через `update_task_upload_id()`

**Что можно делать:**
- 📊 Отслеживать все загруженные видео
- 🔗 Генерировать прямые ссылки на видео
- 📈 Анализировать статистику загрузок
- 🔍 Быстро найти видео по task ID

