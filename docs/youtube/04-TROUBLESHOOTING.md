# 📺 YouTube Automation - Troubleshooting

Решение типичных проблем и отладка YouTube автоматизации.

---

## 📋 Содержание

1. [Проблемы с импортами](#проблемы-с-импортами)
2. [Проблемы с OAuth](#проблемы-с-oauth)
3. [Проблемы с токенами](#проблемы-с-токенами)
4. [Проблемы с базой данных](#проблемы-с-базой-данных)
5. [Проблемы с публикацией](#проблемы-с-публикацией)
6. [Проблемы с квотами](#проблемы-с-квотами)
7. [Отладка](#отладка)

---

## 🐛 Проблемы с импортами

### ❌ Ошибка: `No module named 'src.database_config_loader'`

**Проблема:** Использованы старые пути импорта

**Решение:**
```bash
# Проверьте, что используются правильные импорты
grep "from src\." scripts/*.py

# Должны быть:
from core.utils.database_config_loader import DatabaseConfigLoader
from core.database.mysql_db import get_mysql_database
from core.database.mysql_db import YouTubeMySQLDatabase
```

**Исправление в коде:**
```python
# ❌ СТАРОЕ (неправильно)
from src.database_config_loader import DatabaseConfigLoader
from src.database import get_database_by_type

# ✅ НОВОЕ (правильно)
from core.utils.database_config_loader import DatabaseConfigLoader
from core.database.mysql_db import get_mysql_database
```

### ❌ Ошибка: `ImportError: cannot import name 'get_database_by_type'`

**Проблема:** Неправильный путь импорта

**Решение:**
```python
# ✅ Правильный импорт
from core.database.mysql_db import get_mysql_database

# Использование
db = get_mysql_database()  # Использует MySQL
```

---

## 🔐 Проблемы с OAuth

### ❌ Ошибка: "Access blocked: This app's request is invalid"

**Причина:** Google аккаунт не добавлен в Test Users

**Решение:**
1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. **APIs & Services** → **OAuth consent screen**
3. Прокрутите до **"Test users"**
4. Нажмите **"Add Users"**
5. Добавьте Google email, с которого хотите публиковать
6. Сохраните и попробуйте снова

### ❌ Ошибка: "Redirect URI mismatch"

**Причина:** OAuth настроен на неправильный redirect URI

**Решение:**
1. **Google Cloud Console** → **Credentials**
2. Выберите ваш OAuth Client ID
3. В **"Authorized redirect URIs"** должно быть:
   ```
   http://localhost:8080/callback
   http://localhost:8080
   ```
4. Сохраните

### ❌ Ошибка: "Address already in use" (Port 8080)

**Причина:** Порт 8080 занят другим процессом

**Решение:**
```bash
# Найти процесс на порту 8080
lsof -i :8080

# Результат:
# COMMAND   PID   USER
# python    12345 user

# Завершить процесс
kill -9 12345

# Или использовать другой метод
pkill -f "account_manager.py"

# Попробовать снова
python scripts/account_manager.py authorize --platform youtube --account "Канал"
```

### ❌ Ошибка: "Не удалось создать URL авторизации"

**Причина:** Отсутствуют credentials в `.env` или базе данных

**Решение:**
```bash
# 1. Проверьте .env файл
cat .env | grep YOUTUBE

# Должно быть:
# YOUTUBE_MAIN_CLIENT_ID=123456789-abc.apps.googleusercontent.com
# YOUTUBE_MAIN_CLIENT_SECRET=GOCSPX-xyz...

# 2. Если пусто, добавьте credentials
echo "YOUTUBE_MAIN_CLIENT_ID=your_client_id" >> .env
echo "YOUTUBE_MAIN_CLIENT_SECRET=your_secret" >> .env

# 3. Проверьте credentials.json
ls -la credentials.json
cat credentials.json | grep client_id

# 4. Проверьте канал в базе
python scripts/account_manager.py db list
```

---

## 🔑 Проблемы с токенами

### ❌ Ошибка: "Token expired"

**Причина:** Access token истёк, не удалось обновить

**Решение:**
```bash
# 1. Проверьте статус токенов
python run_youtube_manager.py check-tokens

# 2. Найдите истёкшие каналы
# Вывод: ⚠️ Мой Канал: Токен истек

# 3. Переавторизуйте канал
python scripts/account_manager.py authorize --platform youtube --account "Мой Канал"

# 4. Проверьте снова
python run_youtube_manager.py check-tokens
# Вывод: ✅ Мой Канал: Токен действителен
```

### ❌ Ошибка: "No refresh token available"

**Причина:** Refresh token не был сохранён при авторизации

**Решение:**
```bash
# 1. Удалите старые токены
python scripts/account_manager.py db remove "Мой Канал"

# 2. Добавьте канал заново
python scripts/account_manager.py add-channel "Мой Канал" "@mychannel" --auto-auth

# 3. При авторизации убедитесь, что:
#    - Используется prompt=consent (в OAuthManager)
#    - Выбран правильный Google аккаунт
```

### ❌ Ошибка: "Invalid grant"

**Причина:** Refresh token был отозван или истёк

**Возможные причины:**
- Пользователь отозвал доступ в Google Account settings
- Прошло > 6 месяцев без использования
- Изменены scopes в OAuth Consent Screen

**Решение:**
```bash
# Полная переавторизация
python scripts/account_manager.py authorize --platform youtube --account "Канал"
```

---

## 🗄️ Проблемы с базой данных

### ❌ Ошибка: "Channel not found"

**Причина:** Канал не добавлен в базу данных

**Решение:**
```bash
# 1. Проверьте список каналов
python scripts/account_manager.py db list

# 2. Если канал отсутствует, добавьте его
python scripts/account_manager.py add-channel "Мой Канал" "@mychannel" --auto-auth
```

### ❌ Ошибка: "Channel already exists"

**Причина:** Попытка добавить канал с существующим именем

**Решение:**
```bash
# Вариант 1: Используйте другое имя
python scripts/account_manager.py add-channel "Мой Канал 2" "@mychannel" --auto-auth

# Вариант 2: Удалите старый канал
python scripts/account_manager.py db remove "Мой Канал"
python scripts/account_manager.py add-channel "Мой Канал" "@mychannel" --auto-auth
```

### ❌ Ошибка: "Can't connect to MySQL server"

**Причина:** MySQL сервер не запущен или неправильная конфигурация

**Решение:**
```bash
# 1. Проверьте Docker контейнер
docker ps | grep mysql

# 2. Если не запущен, запустите
cd docker
docker-compose up -d

# 3. Проверьте подключение
mysql -h localhost -P 3306 -u content_fabric -p

# 4. Проверьте config/mysql_config.yaml
cat config/mysql_config.yaml

# 5. Проверьте .env
cat .env | grep MYSQL
```

### ❌ Ошибка: "Table 'youtube_channels' doesn't exist"

**Причина:** База данных не инициализирована

**Решение:**
```bash
# Создайте схему базы данных
python run_setup_database.py

# Для MySQL вручную:
mysql -u content_fabric -p content_fabric < config/mysql_schema.sql
```

---

## 📤 Проблемы с публикацией

### ❌ Ошибка: "Insufficient permissions"

**Причина:** OAuth scopes недостаточны

**Решение:**
1. **Google Cloud Console** → **OAuth consent screen**
2. Убедитесь, что добавлены scopes:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`
   - `https://www.googleapis.com/auth/youtube.force-ssl`
3. Переавторизуйте канал:
```bash
python scripts/account_manager.py authorize --platform youtube --account "Канал"
```

### ❌ Ошибка: "Video too large"

**Причина:** Видео превышает лимит (256GB для verified accounts)

**Решение:**
```bash
# Проверьте размер файла
ls -lh video.mp4

# Сжать видео (ffmpeg)
ffmpeg -i video.mp4 -vcodec libx264 -crf 28 video_compressed.mp4

# Рекомендуемые настройки для Shorts:
ffmpeg -i input.mp4 \
  -vf "scale=1080:1920" \
  -c:v libx264 -crf 23 \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  output.mp4
```

### ❌ Ошибка: "The request cannot be completed because you have exceeded your quota"

См. раздел [Проблемы с квотами](#проблемы-с-квотами)

### ❌ Видео не определяется как Shorts

**Причина:** Неправильное соотношение сторон или длительность

**Требования для Shorts:**
- ✅ Соотношение сторон: 9:16 (вертикальное)
- ✅ Разрешение: 1080x1920 (рекомендуется)
- ✅ Длительность: до 60 секунд
- ✅ Хештег #Shorts в названии или описании

**Решение:**
```bash
# Проверьте свойства видео
ffprobe video.mp4

# Конвертация в правильный формат
ffmpeg -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -preset slow -crf 22 \
  -c:a aac -b:a 128k \
  -t 60 \
  output_shorts.mp4
```

---

## 📊 Проблемы с квотами

### ❌ Ошибка: "Quota exceeded for quota metric 'Queries' and limit 'Queries per day'"

**Причина:** Превышен дневной лимит YouTube Data API (10,000 units)

**Стоимость операций:**
- Upload video: ~1,600 units
- List videos: 1 unit
- Update video: 50 units

**Решение:**

**Вариант 1: Ждать reset (в полночь Pacific Time)**
```bash
# Проверьте текущее время Pacific
TZ='America/Los_Angeles' date

# Quota сбрасывается в 00:00 PT
```

**Вариант 2: Использовать несколько OAuth проектов**
```bash
# Создайте новый проект в Google Cloud Console
# Получите новые credentials
# Добавьте канал с новыми credentials

python run_youtube_manager.py add "Канал 2" \
  --channel-id "@channel2" \
  --client-id "NEW_CLIENT_ID" \
  --client-secret "NEW_SECRET"
```

**Вариант 3: Запросить расширение квоты**
1. **Google Cloud Console** → **APIs & Services** → **Quotas**
2. Найдите "YouTube Data API v3"
3. Request quota increase

### ❌ Ошибка: "Rate limit exceeded"

**Причина:** Слишком много запросов в короткий период

**Решение:**
```python
# Система автоматически использует backoff через BaseAPIClient
# Но можно добавить задержку между загрузками:

import time

for video in videos:
    upload_video(video)
    time.sleep(60)  # Подождать 1 минуту между загрузками
```

---

## 🔍 Отладка

### Просмотр логов

```bash
# Все логи
tail -f logs/auto_posting.log

# Только YouTube
tail -f logs/auto_posting.log | grep YouTube

# Только ошибки
tail -f logs/auto_posting.log | grep ERROR

# Последние 100 строк
tail -n 100 logs/auto_posting.log

# Логи определённого канала
tail -f logs/auto_posting.log | grep "Мой Канал"
```

### Проверка конфигурации

```bash
# 1. Проверка credentials.json
if [ -f credentials.json ]; then
    echo "✅ credentials.json exists"
    cat credentials.json | jq '.installed.client_id'
else
    echo "❌ credentials.json not found"
fi

# 2. Проверка .env
echo "=== .env configuration ==="
cat .env | grep YOUTUBE

# 3. Проверка базы данных
echo "=== Database status ==="
python scripts/account_manager.py db list

# 4. Проверка токенов
echo "=== Token status ==="
python run_youtube_manager.py check-tokens
```

### Тестирование подключения

```bash
# Python interactive test
python3 << EOF
from core.database.mysql_db import get_mysql_database
from core.auth.oauth_manager import OAuthManager

# Test database
db = get_database_by_type()
channels = db.get_all_channels()
print(f"Found {len(channels)} channels")

# Test OAuth
oauth = OAuthManager(use_database=True)
print("OAuth Manager initialized")
EOF
```

### Debug mode

**Включение debug логов:**

```python
# В начале скрипта
import logging
logging.basicConfig(level=logging.DEBUG)

# Для конкретного модуля
logger = logging.getLogger('core.api_clients.youtube_db_client')
logger.setLevel(logging.DEBUG)
```

**Через environment variable:**
```bash
export LOGLEVEL=DEBUG
python scripts/account_manager.py db list
```

---

## 📋 Checklist для диагностики

### Общая диагностика

- [ ] Проверьте Python версию: `python --version` (требуется 3.10+)
- [ ] Проверьте установленные зависимости: `pip list | grep google`
- [ ] Проверьте наличие `credentials.json`: `ls -la credentials.json`
- [ ] Проверьте `.env` файл: `cat .env | grep YOUTUBE`
- [ ] Проверьте логи: `tail -n 50 logs/auto_posting.log`

### OAuth диагностика

- [ ] Google аккаунт добавлен в Test Users (GCP Console)
- [ ] Scopes настроены правильно
- [ ] Порт 8080 свободен: `lsof -i :8080`
- [ ] Redirect URIs настроены: `http://localhost:8080/callback`

### Database диагностика

- [ ] База данных MySQL настроена и доступна
- [ ] Подключение к MySQL работает: `mysql -h localhost -u content_fabric -p`
- [ ] Каналы есть в базе: `python scripts/account_manager.py db list`
- [ ] Токены не истекли: `python run_youtube_manager.py check-tokens`

### Публикация диагностика

- [ ] Видео файл существует и доступен для чтения
- [ ] Формат видео правильный: MP4 или MOV
- [ ] Для Shorts: 9:16, до 60 секунд
- [ ] Канал авторизован и токен действителен
- [ ] Квота не исчерпана

---

## 🆘 Частые вопросы (FAQ)

### Q: Как переавторизовать все каналы?

```bash
# Получить список всех каналов
python scripts/account_manager.py db list

# Авторизовать каждый по очереди
python scripts/account_manager.py authorize --platform youtube --account "Канал 1"
python scripts/account_manager.py authorize --platform youtube --account "Канал 2"
python scripts/account_manager.py authorize --platform youtube --account "Канал 3"
```

### Q: Как настроить MySQL базу данных?

```bash
# 1. Настройте MySQL через Docker
cd docker
docker-compose up -d

# 2. Создайте схему базы данных
python run_setup_database.py

# 3. Настройте переменные окружения в .env
# MYSQL_HOST=localhost
# MYSQL_PORT=3306
# MYSQL_DATABASE=content_fabric
# MYSQL_USER=content_fabric_user
# MYSQL_PASSWORD=your_password

# 4. Проверьте подключение
python scripts/test_integration.py
```

### Q: Как добавить канал с другого Google аккаунта?

```bash
# 1. Добавьте Google аккаунт в Test Users (GCP Console)
# 2. Добавьте канал через CLI
python scripts/account_manager.py add-channel "Другой аккаунт" "@other" --auto-auth

# 3. В браузере войдите в ДРУГОЙ Google аккаунт
# 4. Разрешите доступ
# 5. Готово! Канал использует тот же OAuth Client ID, но другой Google аккаунт
```

### Q: Как удалить все данные и начать заново?

```bash
# ⚠️ ВНИМАНИЕ: Это удалит ВСЕ каналы и токены

# MySQL
mysql -u content_fabric -p -e "DROP DATABASE content_fabric; CREATE DATABASE content_fabric;"
python run_setup_database.py

# Начните заново
python scripts/account_manager.py add-channel "Первый канал" "@first" --auto-auth
```

---

## 📞 Получение помощи

### Шаги для получения поддержки

1. **Соберите информацию:**
```bash
# Создайте diagnostic report
cat > diagnostic.txt << EOF
=== System Info ===
Python: $(python --version)
OS: $(uname -a)

=== Channels ===
$(python scripts/account_manager.py db list)

=== Tokens ===
$(python run_youtube_manager.py check-tokens)

=== Recent Logs ===
$(tail -n 50 logs/auto_posting.log)
EOF

cat diagnostic.txt
```

2. **Проверьте документацию:**
   - [Setup Guide](01-SETUP.md)
   - [CLI Guide](02-CLI-GUIDE.md)
   - [Architecture](03-ARCHITECTURE.md)

3. **Создайте issue** с информацией из diagnostic.txt

---

## 🛠️ Полезные команды для копирования

```bash
# Быстрая диагностика
python scripts/account_manager.py db list && python run_youtube_manager.py check-tokens

# Полная переавторизация
python scripts/account_manager.py authorize --platform youtube --account "YOUR_CHANNEL"

# Проверка логов
tail -f logs/auto_posting.log | grep -E "(ERROR|WARNING|YouTube)"

# Проверка порта
lsof -i :8080 && echo "Port 8080 is in use!" || echo "Port 8080 is free"

# Проверка credentials
test -f credentials.json && echo "✅ credentials.json exists" || echo "❌ credentials.json missing"
test -f .env && echo "✅ .env exists" || echo "❌ .env missing"
cat .env | grep YOUTUBE | wc -l | xargs -I {} echo "Found {} YouTube env vars"
```

---

**Предыдущий:** [← Architecture](03-ARCHITECTURE.md)  
**Главная:** [README](README.md)

