# 🔄 Полный workflow работы с несколькими консолями

Полное описание того, как работает система от начала до конца.

---

## 📋 Общая схема

```
1. Добавление консолей → 2. Назначение каналам → 3. Создание задач → 4. Публикация
```

---

## Шаг 1: Добавление Google Cloud Console

### Что происходит:

```bash
python3 scripts/account_manager.py console add "Console 1" \
  "client-id" "client-secret" \
  --project-id "project-123" \
  --redirect-uris "http://localhost"
```

**В БД создается запись:**
```sql
INSERT INTO google_consoles (
    name, project_id, client_id, client_secret, redirect_uris
) VALUES (
    'Console 1', 'project-123', 'client-id', 'client-secret', '["http://localhost"]'
);
```

**Результат:** Консоль сохранена в БД, готова к использованию.

---

## Шаг 2: Назначение консоли каналу

### Вариант A: При добавлении нового канала

```bash
python3 scripts/account_manager.py add-channel "My Channel" "@channel" \
  --console "Console 1"
```

**В БД:**
```sql
INSERT INTO youtube_channels (
    name, channel_id, console_id, client_id, client_secret
) VALUES (
    'My Channel', '@channel', 1, '...', '...'
);
```

### Вариант B: Для существующего канала

```bash
python3 scripts/account_manager.py set-console "My Channel" "Console 1"
```

**В БД:**
```sql
UPDATE youtube_channels 
SET console_id = 1 
WHERE name = 'My Channel';
```

**Результат:** Канал привязан к консоли.

---

## Шаг 3: Загрузка конфигурации

### При запуске приложения:

1. **DatabaseConfigLoader** загружает каналы из БД:
   ```python
   channels = db.get_all_channels(enabled_only=True)
   ```

2. **Для каждого канала:**
   - Проверяет наличие `console_id`
   - Если есть → загружает консоль из БД
   - Использует `client_id` и `client_secret` из консоли
   - Если нет → использует credentials из канала

3. **Создает config:**
   ```python
   config['accounts']['youtube'] = [
       {
           'name': 'My Channel',
           'channel_id': '@channel',
           'client_id': '...',  # ← Из консоли!
           'client_secret': '...',  # ← Из консоли!
           'console_id': 1,
           'access_token': '...',
           'refresh_token': '...'
       }
   ]
   ```

**Результат:** Приложение знает, какие credentials использовать для каждого канала.

---

## Шаг 4: Создание задачи на публикацию

### Через Task Manager:

```bash
python3 scripts/task_manager.py add \
  --channel "My Channel" \
  --video "/path/to/video.mp4" \
  --title "Video Title" \
  --date "2025-01-26 12:00:00"
```

**В БД создается задача:**
```sql
INSERT INTO tasks (
    account_id,  -- ID канала (не консоли!)
    media_type, title, att_file_path, date_post
) VALUES (
    1, 'youtube', 'Video Title', '/path/to/video.mp4', '2025-01-26 12:00:00'
);
```

**Результат:** Задача создана, привязана к каналу.

---

## Шаг 5: Task Worker обрабатывает задачу

### Процесс обработки:

1. **Получает задачу из БД:**
   ```python
   task = db.get_task(task_id)
   # task.account_id = 1 (ID канала)
   ```

2. **Загружает канал:**
   ```python
   channel = db.get_channel_by_id(task.account_id)
   # channel.console_id = 1 (ID консоли)
   ```

3. **Проверяет консоль:**
   ```python
   if channel.console_id:
       console = db.get_console(channel.console_id)
       # Использует credentials из консоли
       channel.client_id = console.client_id
       channel.client_secret = console.client_secret
   ```

4. **Создает account_info:**
   ```python
   account_info = {
       'name': channel.name,
       'channel_id': channel.channel_id,
       'access_token': channel.access_token,      # Токен канала
       'refresh_token': channel.refresh_token,    # Токен канала
       'client_id': channel.client_id,            # ← Из консоли!
       'client_secret': channel.client_secret     # ← Из консоли!
   }
   ```

5. **Загружает видео:**
   ```python
   youtube_client.post_video(
       account_info=account_info,
       video_path=task.att_file_path,
       ...
   )
   ```

**Результат:** Видео загружается с использованием credentials из консоли.

---

## Шаг 6: YouTubeClient использует credentials

### В методе `_create_service_with_token()`:

```python
# Получает client_id и client_secret из account_info
client_id = account_info.get('client_id', self.client_id)  # ← Из консоли!
client_secret = account_info.get('client_secret', self.client_secret)  # ← Из консоли!

# Создает credentials
creds = Credentials(
    token=access_token,           # Токен канала
    refresh_token=refresh_token,  # Токен канала
    client_id=client_id,          # ← Из консоли!
    client_secret=client_secret,  # ← Из консоли!
    ...
)
```

**Результат:** API запрос использует правильные credentials и тратит квоту правильной консоли.

---

## 📊 Полный пример

### Настройка:

```bash
# 1. Добавить консоли
python3 scripts/account_manager.py console add "Prod Console" \
  "client-id-1" "secret-1" --project-id "project-1"

python3 scripts/account_manager.py console add "Dev Console" \
  "client-id-2" "secret-2" --project-id "project-2"

# 2. Добавить каналы с консолями
python3 scripts/account_manager.py add-channel "Channel 1" "@channel1" \
  --console "Prod Console"

python3 scripts/account_manager.py add-channel "Channel 2" "@channel2" \
  --console "Dev Console"
```

### Публикация:

```bash
# 3. Создать задачи
python3 scripts/task_manager.py add \
  --channel "Channel 1" \
  --video "/path/video1.mp4" \
  --title "Video 1" \
  --date "2025-01-26 12:00:00"

python3 scripts/task_manager.py add \
  --channel "Channel 2" \
  --video "/path/video2.mp4" \
  --title "Video 2" \
  --date "2025-01-26 13:00:00"
```

### Что происходит:

1. **12:00:00** - Task Worker обрабатывает задачу для Channel 1:
   - Загружает Channel 1 → находит console_id = 1 (Prod Console)
   - Использует credentials из Prod Console
   - Загружает видео → тратит квоту Prod Console (10,000 единиц/день)

2. **13:00:00** - Task Worker обрабатывает задачу для Channel 2:
   - Загружает Channel 2 → находит console_id = 2 (Dev Console)
   - Использует credentials из Dev Console
   - Загружает видео → тратит квоту Dev Console (10,000 единиц/день)

**Итого:**
- Channel 1 использует квоту Prod Console
- Channel 2 использует квоту Dev Console
- Общая доступная квота: **20,000 единиц/день**

---

## 🔑 Ключевые моменты

### 1. Автоматическое определение

Система **автоматически**:
- Определяет, какая консоль назначена каналу
- Использует правильные credentials
- Распределяет квоту между консолями

**Вам не нужно ничего менять в коде создания задач!**

### 2. Токены vs Credentials

- **Токены** (access_token, refresh_token) → привязаны к каналу
- **Credentials** (client_id, client_secret) → берутся из консоли (если назначена)

### 3. Fallback механизм

Если консоль не назначена:
1. Используются credentials из канала
2. Если их нет → используются из `.env` (`YOUTUBE_MAIN_CLIENT_ID`)

---

## 📈 Преимущества

### До (одна консоль):
- 10,000 единиц квоты/день
- Все каналы используют одну квоту
- Быстро достигается лимит

### После (несколько консолей):
- 10,000 × количество консолей единиц/день
- Каналы распределены между консолями
- Можно масштабировать без ограничений

---

## 🔍 Проверка работы

### Просмотр назначений:

```bash
# Каналы и их консоли
python3 scripts/account_manager.py db list

# Список консолей
python3 scripts/account_manager.py console list
```

### SQL запрос:

```sql
SELECT 
    c.name as channel,
    g.name as console,
    g.project_id,
    COUNT(t.id) as tasks_count
FROM youtube_channels c
LEFT JOIN google_consoles g ON c.console_id = g.id
LEFT JOIN tasks t ON t.account_id = c.id
WHERE c.enabled = 1
GROUP BY c.id, g.id;
```

---

## ✅ Итог

**Система работает полностью автоматически:**

1. ✅ Добавляете консоли
2. ✅ Назначаете их каналам
3. ✅ Создаете задачи как обычно
4. ✅ Система сама использует правильную консоль для каждого канала
5. ✅ Квота распределяется автоматически

**Никаких изменений в процессе создания задач не требуется!**

---

**Последнее обновление:** 2025-01-XX

