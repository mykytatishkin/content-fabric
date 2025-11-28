# 📺 Публикация на YouTube с системой Google Consoles

## 🔄 Как работает публикация

### Процесс публикации:

```
1. Task Worker получает задачу из БД
   ↓
2. Получает канал по account_id
   ↓
3. Вызывает get_console_credentials_for_channel(channel.name)
   ├─ Если есть console_name → берет из google_consoles
   ├─ Если нет console_name → fallback на channel.client_id/client_secret
   └─ Возвращает: client_id, client_secret, credentials_file
   ↓
4. Инициализирует YouTubeClient с этими credentials
   ↓
5. Использует токены канала (access_token, refresh_token)
   ↓
6. Если токен истек → автоматически обновляет через refresh_token
   ↓
7. Загружает видео на YouTube
```

### Ключевые моменты:

- **Credentials берутся из `google_consoles`** по `console_name` канала
- **Токены хранятся в `youtube_channels`** (access_token, refresh_token)
- **Автоматическое обновление токенов** работает, если токен выдан для правильной консоли
- **Каждая консоль имеет свой независимый квот** YouTube API

---

## 🔐 Переавторизация каналов

### Когда нужна переавторизация:

1. **Ошибка `unauthorized_client: Unauthorized`**
   - Токен был выдан для другой консоли
   - Нужно переавторизовать с правильной консолью

2. **Ошибка `invalid_grant: Token has been expired or revoked`**
   - Токен отозван или истек
   - Нужна новая авторизация

3. **Смена консоли канала**
   - Если изменили `console_name` канала
   - Старый токен не будет работать с новой консолью

4. **Профилактическая переавторизация**
   - Перед важными операциями
   - Если долго не использовали канал

---

## 🛠️ Как переавторизовать канал

### Вариант 1: Через скрипт переавторизации (рекомендуется)

```bash
# Один канал
python3 run_youtube_reauth.py "Channel Name" --redirect-port 9090

# Несколько каналов
python3 run_youtube_reauth.py "Channel 1" "Channel 2" --redirect-port 9090

# Все каналы с истекшими токенами
python3 run_youtube_reauth.py --all-expiring --redirect-port 9090
```

**Важно:** Скрипт автоматически использует правильную консоль из `console_name`!

### Вариант 2: Вручную через Python

```python
from core.database.mysql_db import get_mysql_database
from core.auth.reauth.service import YouTubeReauthService, ServiceConfig

db = get_mysql_database()
config = ServiceConfig()
service = YouTubeReauthService(db=db, service_config=config)

# Переавторизовать один канал
results = service.run_sync(["Channel Name"])

# Проверить результат
for result in results:
    if result.status == result.status.SUCCESS:
        print(f"✅ {result.channel_name} переавторизован")
    else:
        print(f"❌ {result.channel_name}: {result.error}")
```

---

## ⚠️ Автоматическая переавторизация

### ❌ НЕ происходит автоматически:

- При смене `console_name` канала
- При ошибке `unauthorized_client`
- При ошибке `invalid_grant` (только логируется)

### ✅ Происходит автоматически:

- Обновление токена через `refresh_token` (если токен выдан для правильной консоли)
- Обнаружение ошибок авторизации (логирование и уведомления)

---

## 📋 Чеклист при смене консоли канала

Если вы меняете `console_name` канала, нужно:

1. **Обновить `console_name` в БД:**
   ```sql
   UPDATE youtube_channels 
   SET console_name = 'New Console Name' 
   WHERE name = 'Channel Name';
   ```

2. **Переавторизовать канал:**
   ```bash
   python3 run_youtube_reauth.py "Channel Name" --redirect-port 9090
   ```

3. **Проверить, что токены обновлены:**
   ```python
   channel = db.get_channel("Channel Name")
   print(f"Access Token: {channel.access_token[:20]}...")
   print(f"Console: {channel.console_name}")
   ```

---

## 🔍 Проверка конфигурации

### Проверить, какая консоль используется:

```python
from core.database.mysql_db import get_mysql_database

db = get_mysql_database()
channel = db.get_channel("Channel Name")

print(f"Канал: {channel.name}")
print(f"Console Name: {channel.console_name or 'НЕ УСТАНОВЛЕНО'}")

credentials = db.get_console_credentials_for_channel(channel.name)
if credentials:
    print(f"Client ID: {credentials['client_id'][:30]}...")
    console = db.get_google_console(channel.console_name) if channel.console_name else None
    if console:
        print(f"Консоль: {console.name}")
        print(f"Description: {console.description}")
```

---

## 🎯 Рекомендации

1. **Всегда привязывайте каналы к консолям** через `console_name`
2. **Переавторизуйте каналы после смены консоли**
3. **Используйте разные консоли** для распределения квоты API
4. **Проверяйте токены** перед важными операциями
5. **Мониторьте ошибки** `unauthorized_client` и `invalid_grant`

---

## 📝 Примеры

### Пример 1: Привязка канала к консоли и переавторизация

```python
from core.database.mysql_db import get_mysql_database

db = get_mysql_database()

# 1. Привязываем канал к консоли
db._execute_query(
    "UPDATE youtube_channels SET console_name = %s WHERE name = %s",
    ("Console 1", "My Channel")
)

# 2. Переавторизуем
from core.auth.reauth.service import YouTubeReauthService, ServiceConfig
service = YouTubeReauthService(db=db, service_config=ServiceConfig())
results = service.run_sync(["My Channel"])

# 3. Проверяем
channel = db.get_channel("My Channel")
print(f"Console: {channel.console_name}")
print(f"Token: {channel.access_token[:20] if channel.access_token else 'None'}...")
```

### Пример 2: Массовая переавторизация всех каналов

```bash
# Через скрипт
python3 run_youtube_reauth.py --all-expiring --redirect-port 9090

# Или через Python
python3 -c "
from core.database.mysql_db import get_mysql_database
from core.auth.reauth.service import YouTubeReauthService, ServiceConfig

db = get_mysql_database()
channels = [c.name for c in db.get_all_channels(enabled_only=True)]
service = YouTubeReauthService(db=db, service_config=ServiceConfig())
results = service.run_sync(channels)
print(f'Успешно: {sum(1 for r in results if r.status == r.status.SUCCESS)}')
print(f'Ошибок: {sum(1 for r in results if r.status != r.status.SUCCESS)}')
"
```

