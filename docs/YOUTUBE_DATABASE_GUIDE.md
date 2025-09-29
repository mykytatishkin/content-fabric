# 🗄️ YouTube Database Integration Guide

## 📋 Обзор

Система YouTube Database Integration позволяет управлять множественными YouTube каналами через базу данных SQLite, что упрощает масштабирование и управление токенами.

## 🎯 Преимущества

- ✅ **Один файл credentials.json** для всех каналов
- ✅ **Токены в БД** вместо множества файлов
- ✅ **Динамическое управление** каналами
- ✅ **Безопасное хранение** токенов
- ✅ **Простое масштабирование**
- ✅ **Автоматическое обновление** токенов

## 🏗️ Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   config.yaml   │───▶│  Migration Tool  │───▶│  SQLite Database│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐            │
│  YouTube Client │◀───│  Database Client │◀───────────┘
└─────────────────┘    └──────────────────┘
```

## 📁 Структура файлов

```
content-fabric/
├── src/
│   ├── database.py              # Модуль работы с БД
│   └── api_clients/
│       └── youtube_db_client.py # YouTube клиент с БД
├── youtube_db_manager.py        # CLI для управления каналами
├── migrate_to_db.py            # Миграция из config.yaml
├── test_youtube_db.py          # Тестирование системы
├── youtube_channels.db         # SQLite база данных
└── credentials.json            # Единый OAuth файл
```

## 🚀 Быстрый старт

### 1. Миграция существующих каналов

```bash
# Мигрировать каналы из config.yaml в БД
python3 migrate_to_db.py
```

### 2. Управление каналами

```bash
# Показать все каналы
python3 youtube_db_manager.py list

# Добавить новый канал
python3 youtube_db_manager.py add "Новый канал" \
  --channel-id "UC1234567890" \
  --client-id "ваш_client_id" \
  --client-secret "ваш_client_secret"

# Включить/отключить канал
python3 youtube_db_manager.py enable "Новый канал"
python3 youtube_db_manager.py disable "Новый канал"

# Проверить статус токенов
python3 youtube_db_manager.py check-tokens
```

### 3. Публикация на несколько каналов

```bash
# Публикация на все включенные каналы
python3 main.py post \
  --content content/videos/video.mp4 \
  --caption "Заголовок видео\nОписание видео" \
  --platforms youtube

# Публикация на конкретные каналы
python3 main.py post \
  --content content/videos/video.mp4 \
  --caption "Заголовок видео" \
  --platforms youtube \
  --accounts "Teasera,Andrew Garle"
```

## 🔧 Настройка

### 1. Google Cloud Console

Создайте **один** OAuth 2.0 Client ID типа "Desktop application":

1. **APIs & Services → Credentials**
2. **Create Credentials → OAuth 2.0 Client ID**
3. **Application type: Desktop application**
4. **Download JSON** как `credentials.json`

### 2. Переменные окружения (.env)

```bash
# Для каждого канала (если нужны разные аккаунты)
YOUTUBE_TEASERA_CLIENT_ID=ваш_client_id_teasera
YOUTUBE_TEASERA_CLIENT_SECRET=ваш_client_secret_teasera

YOUTUBE_ANDREW_CLIENT_ID=ваш_client_id_andrew
YOUTUBE_ANDREW_CLIENT_SECRET=ваш_client_secret_andrew

# Или используйте один OAuth клиент для всех каналов
YOUTUBE_MAIN_CLIENT_ID=ваш_основной_client_id
YOUTUBE_MAIN_CLIENT_SECRET=ваш_основной_client_secret
```

### 3. Структура базы данных

#### Таблица `youtube_channels`:
```sql
CREATE TABLE youtube_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- Название канала
    channel_id TEXT NOT NULL,            -- ID канала
    client_id TEXT NOT NULL,             -- OAuth Client ID
    client_secret TEXT NOT NULL,         -- OAuth Client Secret
    access_token TEXT,                   -- Access Token
    refresh_token TEXT,                  -- Refresh Token
    token_expires_at TEXT,               -- Время истечения токена
    enabled BOOLEAN DEFAULT 1,           -- Включен ли канал
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## 📚 API Reference

### YouTubeDatabase

#### Основные методы:

```python
from src.database import get_database

db = get_database()

# Добавить канал
db.add_channel(name, channel_id, client_id, client_secret, enabled=True)

# Получить канал
channel = db.get_channel(name)

# Получить все каналы
channels = db.get_all_channels(enabled_only=True)

# Обновить токены
db.update_channel_tokens(name, access_token, refresh_token, expires_at)

# Проверить истечение токена
is_expired = db.is_token_expired(name)
```

### YouTubeDBClient

#### Основные методы:

```python
from src.api_clients.youtube_db_client import YouTubeDBClient

client = YouTubeDBClient()

# Получить доступные каналы
channels = client.get_available_channels()

# Установить канал
client.set_channel("Teasera")

# Публикация на один канал
result = client.post_to_channel("Teasera", "video.mp4", "Заголовок", "Описание")

# Публикация на несколько каналов
results = client.post_to_multiple_channels(
    ["Teasera", "Andrew Garle"], 
    "video.mp4", 
    "Заголовок", 
    "Описание"
)
```

## 🛠️ CLI Commands

### youtube_db_manager.py

```bash
# Список команд
python3 youtube_db_manager.py --help

# Добавить канал
python3 youtube_db_manager.py add "Название" \
  --channel-id "ID" \
  --client-id "CLIENT_ID" \
  --client-secret "CLIENT_SECRET"

# Показать каналы
python3 youtube_db_manager.py list [--enabled-only]

# Управление каналами
python3 youtube_db_manager.py enable "Название"
python3 youtube_db_manager.py disable "Название"
python3 youtube_db_manager.py delete "Название"

# Информация о канале
python3 youtube_db_manager.py show "Название"

# Проверка токенов
python3 youtube_db_manager.py check-tokens

# Экспорт/импорт
python3 youtube_db_manager.py export [--output config.json]
python3 youtube_db_manager.py import config.json

# Демо настройка
python3 youtube_db_manager.py setup-demo
```

## 🔐 Безопасность

### Хранение токенов:
- ✅ Токены шифруются в базе данных
- ✅ Автоматическое обновление refresh токенов
- ✅ Проверка истечения токенов
- ✅ Безопасное удаление старых токенов

### OAuth Flow:
1. **Первый запуск**: OAuth авторизация через браузер
2. **Сохранение**: Токены сохраняются в БД
3. **Обновление**: Автоматическое обновление через refresh token
4. **Повторная авторизация**: Только при истечении refresh token

## 🐛 Troubleshooting

### Проблема: "Channel not found"
```bash
# Проверить каналы в БД
python3 youtube_db_manager.py list

# Добавить канал
python3 youtube_db_manager.py add "Название" --channel-id "ID" --client-id "ID" --client-secret "SECRET"
```

### Проблема: "Token expired"
```bash
# Проверить статус токенов
python3 youtube_db_manager.py check-tokens

# Переавторизоваться (удалить токены и запустить заново)
rm youtube_channels.db
python3 migrate_to_db.py
```

### Проблема: "OAuth client not found"
```bash
# Проверить credentials.json
ls -la credentials.json

# Проверить .env файл
cat .env | grep YOUTUBE
```

## 📊 Мониторинг

### Логи:
```bash
# Просмотр логов
tail -f logs/auto_posting.log | grep YouTube
```

### Статистика:
```bash
# Проверка каналов
python3 youtube_db_manager.py list

# Проверка токенов
python3 youtube_db_manager.py check-tokens
```

## 🚀 Production Deployment

### 1. Backup базы данных:
```bash
cp youtube_channels.db youtube_channels.db.backup
```

### 2. Мониторинг:
```bash
# Cron job для проверки токенов
0 */6 * * * cd /path/to/project && python3 youtube_db_manager.py check-tokens
```

### 3. Логирование:
```bash
# Ротация логов
logrotate /etc/logrotate.d/youtube-automation
```

## 📈 Масштабирование

### Добавление новых каналов:
1. **Создать OAuth клиент** (если нужен отдельный аккаунт)
2. **Добавить в .env** переменные
3. **Добавить в БД** через CLI
4. **Протестировать** авторизацию

### Управление множественными аккаунтами:
- **Один OAuth клиент**: Все каналы одного Google аккаунта
- **Множественные OAuth клиенты**: Каждый канал отдельного Google аккаунта

## 🎯 Best Practices

1. **Регулярные бэкапы** базы данных
2. **Мониторинг токенов** каждые 6 часов
3. **Логирование** всех операций
4. **Тестирование** перед production
5. **Ротация логов** для экономии места

---

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `tail -f logs/auto_posting.log`
2. Проверьте статус: `python3 youtube_db_manager.py list`
3. Проверьте токены: `python3 youtube_db_manager.py check-tokens`
4. Создайте issue с подробным описанием проблемы
