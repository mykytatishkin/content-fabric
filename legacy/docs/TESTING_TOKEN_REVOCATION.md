# 🧪 Тестирование автоматической переавторизации при отзыве токена

Это руководство показывает, как протестировать новую функциональность автоматической переавторизации используя существующие инструменты проекта.

## 📋 Способы тестирования

### 1. Проверка токенов (найти канал с отозванным токеном)

```bash
# Проверить все каналы
python3 app/checks/check_refresh_token_validity.py

# Проверить конкретный канал
python3 app/checks/check_refresh_token_validity.py Readbooks-online
```

Этот скрипт покажет:
- ✅ Какие каналы имеют валидные токены
- ❌ Какие каналы имеют отозванные/истекшие токены
- ⚠️ Какие каналы не имеют токенов

**Если канал показывает `invalid_grant`** - это идеальный кандидат для тестирования!

---

### 2. Интерактивное тестирование через Python REPL

Запустите Python в интерактивном режиме:

```bash
python3
```

Затем выполните:

```python
# Импорты
from core.database.mysql_db import get_mysql_database
from app.task_worker import TaskWorker
from core.api_clients.youtube_client import YouTubeClient

# Подключение к БД
db = get_mysql_database()

# Инициализация Task Worker
worker = TaskWorker(db=db, check_interval=60, max_retries=3)

# Получить канал с отозванным токеном
channel_name = "Readbooks-online"  # Замените на ваш канал
channel = db.get_channel(channel_name)

# Найти pending задачу для этого канала
pending_tasks = db.get_pending_tasks()
task = None
for t in pending_tasks:
    if t.account_id == channel.id:
        task = t
        break

if task:
    print(f"Найдена задача #{task.id}: {task.title}")
    
    # Обработать задачу - это вызовет автоматическую переавторизацию
    # если токен отозван
    result = worker.process_single_task(task.id)
    
    print(f"Результат: {'Успешно' if result else 'Ошибка'}")
    
    # Проверить статус переавторизации
    if channel_name in worker.ongoing_reauths:
        print(f"✅ Переавторизация запущена для {channel_name}")
    else:
        print(f"ℹ️  Переавторизация не запущена (возможно, токен валиден)")
else:
    print("Нет pending задач для этого канала")
```

---

### 3. Тестирование через обработку реальной задачи

Если у вас есть задача с отозванным токеном:

```bash
# Запустить Task Worker
python3 run_task_worker.py
```

Task Worker автоматически:
1. Найдет pending задачи
2. Попытается загрузить видео
3. При ошибке `invalid_grant` автоматически запустит переавторизацию
4. Отправит уведомления в Telegram

**Мониторинг:**
- Смотрите логи в консоли
- Проверяйте Telegram на наличие уведомлений
- Проверяйте статус задачи в БД

---

### 4. Быстрый тест через Python one-liner

```bash
python3 -c "
from core.database.mysql_db import get_mysql_database
from app.task_worker import TaskWorker

db = get_mysql_database()
worker = TaskWorker(db=db)

# Найти задачу для канала с отозванным токеном
task_id = 2418  # Замените на ID вашей задачи
result = worker.process_single_task(task_id)
print(f'Результат: {\"Успешно\" if result else \"Ошибка\"}')
"
```

---

### 5. Симуляция ошибки через мок

Если хотите протестировать без реального отозванного токена:

```python
from core.database.mysql_db import get_mysql_database, Task, YouTubeChannel
from app.task_worker import TaskWorker
from core.api_clients.youtube_client import PostResult

db = get_mysql_database()
worker = TaskWorker(db=db)

# Создать мок канал
mock_channel = YouTubeChannel(
    id=99999,
    name="TEST_CHANNEL",
    channel_id="UC_TEST",
    enabled=True
)

# Создать мок задачу
mock_task = Task(
    id=99999,
    title="Test Video",
    description="Test",
    account_id=mock_channel.id,
    media_type="youtube",
    att_file_path="/tmp/test.mp4",
    status=0,
    keywords="test"
)

# Создать мок YouTube клиент, который возвращает ошибку токена
class MockYouTubeClient(YouTubeClient):
    def post_video(self, account_info, video_path, caption, metadata=None):
        return PostResult(
            success=False,
            error_message="invalid_grant: Token has been expired or revoked.",
            platform="YouTube",
            account=account_info.get('name', 'Unknown')
        )

worker.set_youtube_client(MockYouTubeClient(
    client_id="test",
    client_secret="test"
))

# Обработать задачу - это вызовет автоматическую переавторизацию
result = worker._process_youtube_task(mock_task, mock_channel)
print(f"Результат: {result}")
print(f"Переавторизация запущена: {mock_channel.name in worker.ongoing_reauths}")
```

---

## ✅ Что проверить после тестирования

1. **Telegram уведомления:**
   - ✅ Сообщение о начале переавторизации
   - ✅ Сообщение о результате (успех/ошибка)

2. **Логи:**
   ```bash
   # Проверить логи
   tail -f logs/task_worker.log
   # или если запущен в консоли - смотреть вывод
   ```

3. **Статус задачи в БД:**
   ```sql
   SELECT id, title, status, error_message 
   FROM tasks 
   WHERE id = <task_id>;
   ```
   - Статус должен быть `3` (Failed)
   - `error_message` должен содержать информацию об отозванном токене

4. **Статус переавторизации:**
   ```python
   # В Python REPL
   print(worker.ongoing_reauths)  # Должен содержать имя канала во время переавторизации
   ```

5. **Токены в БД:**
   ```sql
   SELECT name, access_token IS NOT NULL as has_access_token,
          refresh_token IS NOT NULL as has_refresh_token,
          token_expires_at
   FROM youtube_channels
   WHERE name = 'Readbooks-online';
   ```
   - После успешной переавторизации должны быть новые токены

---

## 🔍 Диагностика проблем

### Переавторизация не запускается

1. Проверьте, что ошибка содержит ключевые слова:
   - `invalid_grant`
   - `token revoked`
   - `token expired`
   - `re-authenticate`

2. Проверьте логи на наличие ошибок:
   ```bash
   grep -i "token\|reauth" logs/task_worker.log
   ```

3. Проверьте, что канал не находится уже в процессе переавторизации:
   ```python
   print(worker.ongoing_reauths)
   ```

### Telegram уведомления не приходят

1. Проверьте конфигурацию:
   ```bash
   echo $TELEGRAM_BOT_TOKEN
   echo $TELEGRAM_CHAT_ID
   ```

2. Проверьте подписчиков:
   ```python
   from core.utils.telegram_broadcast import TelegramBroadcast
   broadcaster = TelegramBroadcast()
   print(broadcaster.get_subscribers())
   ```

3. Протестируйте отправку вручную:
   ```python
   from core.utils.telegram_broadcast import TelegramBroadcast
   broadcaster = TelegramBroadcast()
   result = broadcaster.broadcast_message("🧪 Test message")
   print(result)
   ```

---

## 📝 Пример полного теста

```bash
# 1. Проверить токены
python3 app/checks/check_refresh_token_validity.py Readbooks-online

# 2. Если токен отозван, найти задачу
python3 -c "
from core.database.mysql_db import get_mysql_database
db = get_mysql_database()
tasks = db.get_pending_tasks()
channel = db.get_channel('Readbooks-online')
for t in tasks:
    if t.account_id == channel.id:
        print(f'Task ID: {t.id}, Title: {t.title}')
        break
"

# 3. Обработать задачу (замените <task_id> на реальный ID)
python3 -c "
from core.database.mysql_db import get_mysql_database
from app.task_worker import TaskWorker
import time

db = get_mysql_database()
worker = TaskWorker(db=db)
task_id = <task_id>  # Замените на реальный ID

print('Обработка задачи...')
result = worker.process_single_task(task_id)
print(f'Результат: {result}')

time.sleep(5)  # Подождать запуска переавторизации
print(f'Переавторизация в процессе: {list(worker.ongoing_reauths)}')
"

# 4. Проверить Telegram - должны прийти уведомления
```

---

## 🎯 Рекомендуемый порядок тестирования

1. **Найти канал с отозванным токеном:**
   ```bash
   python3 app/checks/check_refresh_token_validity.py
   ```

2. **Найти задачу для этого канала:**
   ```sql
   SELECT t.id, t.title, t.status, c.name as channel_name
   FROM tasks t
   JOIN youtube_channels c ON t.account_id = c.id
   WHERE c.name = 'Readbooks-online' AND t.status = 0;
   ```

3. **Обработать задачу через Task Worker:**
   ```python
   from core.database.mysql_db import get_mysql_database
   from app.task_worker import TaskWorker
   
   db = get_mysql_database()
   worker = TaskWorker(db=db)
   worker.process_single_task(2418)  # Замените на ваш task_id
   ```

4. **Проверить результаты:**
   - Telegram уведомления
   - Логи
   - Статус задачи в БД
   - Новые токены в БД (после успешной переавторизации)

---

## 💡 Полезные команды

```bash
# Проверить все каналы с проблемными токенами
python3 app/checks/check_refresh_token_validity.py --all

# Запустить Task Worker для автоматической обработки
python3 run_task_worker.py

# Проверить логи в реальном времени
tail -f logs/task_worker.log | grep -i "reauth\|token\|revocation"

# Проверить подписчиков Telegram
python3 -c "
from core.utils.telegram_broadcast import TelegramBroadcast
print(TelegramBroadcast().get_subscribers())
"
```

