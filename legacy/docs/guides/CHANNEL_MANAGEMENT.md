# 📺 Управление YouTube каналами

Полное руководство по управлению YouTube каналами в Content Fabric.

---

## 🎯 Обзор

Content Fabric поддерживает управление неограниченным количеством YouTube каналов через базу данных MySQL. Каждый канал имеет свои OAuth токены и настройки.

---

## 🚀 Быстрый старт

### Добавление первого канала

```bash
# 1. Добавить канал с автоматической авторизацией
python run_youtube_manager.py add "MyChannel" \
    --channel-id "UCxxxxxxxxxxxxxxxxxxxxx" \
    --auto-auth

# 2. Проверить список каналов
python run_youtube_manager.py list

# 3. Проверить статус токенов
python run_youtube_manager.py check-tokens
```

---

## 📋 Основные команды

### Список каналов

```bash
# Показать все каналы
python run_youtube_manager.py list

# Показать только активные каналы
python run_youtube_manager.py list --enabled

# Показать только неактивные каналы
python run_youtube_manager.py list --disabled
```

**Вывод:**
```
ID  Name              Channel ID          Enabled  Token Status
----------------------------------------------------------------
1   MyChannel         UCxxxxx...          ✅       Valid
2   BackupChannel     UCyyyyy...          ❌       Expired
```

### Добавление канала

```bash
# Минимальная команда (с авторизацией)
python run_youtube_manager.py add "ChannelName" \
    --channel-id "UCxxxxxxxxxxxxxxxxxxxxx" \
    --auto-auth

# С дополнительными параметрами
python run_youtube_manager.py add "ChannelName" \
    --channel-id "UCxxxxxxxxxxxxxxxxxxxxx" \
    --client-id "your_client_id" \
    --client-secret "your_client_secret" \
    --auto-auth

# Без автоматической авторизации (ручная)
python run_youtube_manager.py add "ChannelName" \
    --channel-id "UCxxxxxxxxxxxxxxxxxxxxx"
```

**Параметры:**
- `--channel-id` - ID YouTube канала (обязательно)
- `--client-id` - Google OAuth Client ID (опционально, берется из .env)
- `--client-secret` - Google OAuth Client Secret (опционально, берется из .env)
- `--auto-auth` - Автоматическая авторизация через браузер

### Удаление канала

```bash
# Удалить канал по ID
python run_youtube_manager.py delete 1

# Удалить канал по имени
python run_youtube_manager.py delete "ChannelName"

# Удалить с подтверждением
python run_youtube_manager.py delete 1 --confirm
```

### Обновление канала

```bash
# Изменить имя канала
python run_youtube_manager.py update 1 --name "NewName"

# Включить/отключить канал
python run_youtube_manager.py update 1 --enabled true
python run_youtube_manager.py update 1 --enabled false

# Обновить Channel ID
python run_youtube_manager.py update 1 --channel-id "UCnewid..."
```

### Проверка токенов

```bash
# Проверить все токены
python run_youtube_manager.py check-tokens

# Проверить конкретный канал
python run_youtube_manager.py check-tokens --channel "ChannelName"

# Показать только истекшие токены
python run_youtube_manager.py check-tokens --expired
```

**Вывод:**
```
Channel: MyChannel
  Token Status: ✅ Valid
  Expires At: 2024-12-25 18:00:00
  Time Remaining: 2 hours 30 minutes

Channel: BackupChannel
  Token Status: ❌ Expired
  Expires At: 2024-12-24 10:00:00
  Action Required: Re-authenticate
```

---

## 🔐 Управление авторизацией

### Автоматическая авторизация

```bash
# Авторизовать все каналы
python reauth_multiple_channels.py --all

# Авторизовать конкретный канал
python reauth_multiple_channels.py "ChannelName"

# Авторизовать только истекшие токены
python reauth_multiple_channels.py --expired
```

### Ручная авторизация

1. Получите URL для авторизации:
```bash
python run_youtube_manager.py auth-url "ChannelName"
```

2. Откройте URL в браузере и авторизуйтесь

3. Скопируйте код авторизации из URL

4. Добавьте токен:
```bash
python run_youtube_manager.py add-token "ChannelName" \
    --access-token "ya29.xxxxx" \
    --refresh-token "1//xxxxx" \
    --expires-in 3600
```

### Обновление токенов

```bash
# Обновить все токены
python run_youtube_manager.py refresh-tokens

# Обновить конкретный канал
python run_youtube_manager.py refresh-tokens --channel "ChannelName"
```

---

## 📊 Работа с задачами

### Создание задачи для канала

```bash
python run_task_manager.py create \
    --account "ChannelName" \
    --video "/path/to/video.mp4" \
    --title "Video Title" \
    --description "Description" \
    --keywords "tag1,tag2,tag3" \
    --schedule "2024-12-25 18:00:00"
```

### Публикация на несколько каналов

```bash
# Через main.py
python app/main.py post \
    --content video.mp4 \
    --caption "Caption" \
    --platforms youtube \
    --accounts "Channel1,Channel2,Channel3"
```

---

## 🗄️ Работа с базой данных

### Прямые SQL запросы

```sql
-- Список всех каналов
SELECT id, name, channel_id, enabled, token_expires_at 
FROM youtube_channels;

-- Каналы с истекшими токенами
SELECT id, name, channel_id, token_expires_at 
FROM youtube_channels 
WHERE token_expires_at < NOW();

-- Включить канал
UPDATE youtube_channels 
SET enabled = 1 
WHERE id = 1;

-- Получить токены канала
SELECT access_token, refresh_token, token_expires_at 
FROM youtube_channels 
WHERE name = 'ChannelName';
```

### Программный доступ

```python
from core.database.mysql_db import YouTubeMySQLDatabase

db = YouTubeMySQLDatabase()

# Получить все каналы
channels = db.get_all_channels()
for channel in channels:
    print(f"{channel.name}: {channel.channel_id}")

# Получить канал по имени
channel = db.get_channel("ChannelName")
if channel:
    print(f"Channel ID: {channel.channel_id}")
    print(f"Token expires: {channel.token_expires_at}")

# Добавить канал
channel_id = db.add_channel(
    name="NewChannel",
    channel_id="UCxxxxx...",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

db.close()
```

---

## ⚙️ Конфигурация

### Переменные окружения

```bash
# .env файл
YOUTUBE_MAIN_CLIENT_ID=your_client_id
YOUTUBE_MAIN_CLIENT_SECRET=your_client_secret
```

### Credentials файл

Поместите `credentials.json` в корень проекта:

```json
{
  "installed": {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost"]
  }
}
```

---

## 🔍 Troubleshooting

### Проблема: "Channel not found"

**Решение:**
```bash
# Проверить список каналов
python run_youtube_manager.py list

# Убедиться, что используете правильное имя или ID
python run_task_manager.py create --account "ExactChannelName" ...
```

### Проблема: "Token expired"

**Решение:**
```bash
# Переавторизовать канал
python reauth_multiple_channels.py "ChannelName"

# Или обновить токен
python run_youtube_manager.py refresh-tokens --channel "ChannelName"
```

### Проблема: "Invalid credentials"

**Решение:**
1. Проверьте `.env` файл:
```bash
cat .env | grep YOUTUBE
```

2. Проверьте `credentials.json`:
```bash
cat credentials.json
```

3. Переавторизуйтесь:
```bash
python reauth_multiple_channels.py "ChannelName"
```

### Проблема: "Channel disabled"

**Решение:**
```bash
# Включить канал
python run_youtube_manager.py update "ChannelName" --enabled true
```

---

## 📚 Дополнительные ресурсы

- **[YouTube Setup Guide](../youtube/01-SETUP.md)** - Полная настройка YouTube
- **[YouTube CLI Guide](../youtube/02-CLI-GUIDE.md)** - Детальный гайд по CLI
- **[OAuth Reauth Guide](../reauth/REAUTH_README.md)** - Переавторизация
- **[Task Management](../guides/TASK_MANAGEMENT.md)** - Управление задачами
- **[Multiple Accounts](MULTIPLE_ACCOUNTS.md)** - Работа с множественными аккаунтами

---

## 💡 Best Practices

1. **Используйте понятные имена**: `"Main Channel"` вместо `"channel1"`
2. **Регулярно проверяйте токены**: `python run_youtube_manager.py check-tokens`
3. **Включайте каналы по необходимости**: Отключайте неиспользуемые каналы
4. **Делайте бэкапы**: Регулярно экспортируйте данные из БД
5. **Мониторьте лимиты**: Следите за использованием YouTube API quota

---

**Последнее обновление**: 2025-01-16


