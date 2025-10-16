# 📺 YouTube Automation - Настройка

Полное руководство по настройке YouTube автоматизации с нуля.

---

## 📋 Предварительные требования

- ✅ Google аккаунт с YouTube каналом
- ✅ Python 3.10+
- ✅ Content Fabric проект установлен
- ✅ MySQL база данных (опционально, можно использовать SQLite)

---

## 🔧 Шаг 1: Google Cloud Console

### 1.1 Создание проекта

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Нажмите **"Select a project"** → **"New Project"**
3. Введите название: **"Content Fabric YouTube"**
4. Нажмите **"Create"**

### 1.2 Включение YouTube Data API v3

1. В боковом меню: **APIs & Services** → **Library**
2. Найдите: **"YouTube Data API v3"**
3. Нажмите **"Enable"**

### 1.3 Настройка OAuth Consent Screen

1. Перейдите в **APIs & Services** → **OAuth consent screen**
2. Выберите **External** (для личного использования)
3. Заполните обязательные поля:
   - **App name**: `Content Fabric Auto Poster`
   - **User support email**: ваш email
   - **Developer contact email**: ваш email
4. Нажмите **"Save and Continue"**

### 1.4 Добавление Scopes

1. На странице **"Scopes"** нажмите **"Add or Remove Scopes"**
2. Найдите и добавьте:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`
   - `https://www.googleapis.com/auth/youtube.force-ssl`
3. Нажмите **"Update"** → **"Save and Continue"**

### 1.5 Добавление Test Users

1. На странице **"Test users"** нажмите **"Add Users"**
2. Добавьте ваш Google email
3. Добавьте email-ы всех Google аккаунтов, с которых планируете публиковать
4. Нажмите **"Save and Continue"**

⚠️ **Важно**: Только эти пользователи смогут авторизоваться, пока приложение в тестовом режиме.

### 1.6 Создание OAuth 2.0 Credentials

1. Перейдите в **APIs & Services** → **Credentials**
2. Нажмите **"+ Create Credentials"** → **"OAuth client ID"**
3. Выберите тип: **"Desktop application"**
4. Название: `YouTube Desktop Client`
5. Нажмите **"Create"**
6. **Скачайте JSON файл** (кнопка Download JSON)

---

## 📁 Шаг 2: Настройка проекта

### 2.1 Размещение credentials.json

```bash
# Скопируйте скачанный файл в корень проекта
cp ~/Downloads/client_secret_*.json /path/to/content-fabric/credentials.json
```

**Структура проекта:**
```
content-fabric/
├── credentials.json          # ← Поместите файл сюда
├── .env                      # ← Создадим на следующем шаге
├── scripts/
│   └── account_manager.py
└── ...
```

### 2.2 Создание .env файла

Создайте файл `.env` в корне проекта:

```bash
# YouTube OAuth Credentials
YOUTUBE_MAIN_CLIENT_ID=123456789-abc123def456.apps.googleusercontent.com
YOUTUBE_MAIN_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz

# MySQL Database (если используете)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=content_fabric
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=content_fabric
```

#### Где взять значения?

**Способ 1: Из credentials.json**
```bash
# Посмотрите содержимое файла
cat credentials.json
```

Найдите:
```json
{
  "installed": {
    "client_id": "123456789-abc.apps.googleusercontent.com",    # ← Это YOUTUBE_MAIN_CLIENT_ID
    "client_secret": "GOCSPX-xyz...",                           # ← Это YOUTUBE_MAIN_CLIENT_SECRET
    ...
  }
}
```

**Способ 2: Из Google Cloud Console**
1. **APIs & Services** → **Credentials**
2. Найдите ваш OAuth 2.0 Client ID
3. Скопируйте **Client ID** и **Client secret**

### 2.3 Проверка конфигурации

```bash
# Убедитесь, что файлы на месте
ls -la credentials.json
ls -la .env

# Проверьте содержимое .env
cat .env | grep YOUTUBE
```

---

## 🗄️ Шаг 3: Настройка базы данных

### Вариант A: SQLite (по умолчанию)

SQLite используется автоматически. Никаких дополнительных действий не требуется.

База создастся автоматически при первом запуске: `data/databases/youtube_channels.db`

### Вариант B: MySQL (рекомендуется для production)

1. **Установите MySQL через Docker:**
```bash
cd docker
docker-compose up -d
```

2. **Создайте схему:**
```bash
python run_setup_database.py
```

3. **Настройте переменные в .env** (см. шаг 2.2 выше)

Подробнее: [MySQL Setup Guide](../DOCKER_MYSQL_SETUP.md)

---

## ✅ Шаг 4: Проверка установки

### 4.1 Проверка зависимостей

```bash
# Установите зависимости
pip install -r requirements.txt

# Проверьте импорты
python -c "from core.database.sqlite_db import get_database_by_type; print('✅ OK')"
```

### 4.2 Проверка CLI утилит

```bash
# Проверьте account_manager
python scripts/account_manager.py --help

# Проверьте youtube_manager
python run_youtube_manager.py --help
```

**Ожидаемый вывод:**
```
usage: account_manager.py [-h] {add-channel,authorize,db,migrate,...}
...
```

### 4.3 Проверка базы данных

```bash
# Проверьте подключение к базе
python scripts/account_manager.py db list
```

**Первый запуск:**
```
✅ Connected to MySQL database
📺 Каналы в базе данных:
   Всего: 0
   Включенных: 0
   ...
```

---

## 🎯 Шаг 5: Первый канал

### 5.1 Добавление канала

```bash
# Добавить канал с автоматической авторизацией
python scripts/account_manager.py add-channel "Мой Первый Канал" "@mychannel" --auto-auth
```

**Процесс:**
1. ✅ Канал добавляется в базу данных
2. 🌐 Откроется браузер для авторизации
3. 🔐 Войдите в нужный Google аккаунт
4. ✅ Разрешите доступ
5. ✅ Токены сохраняются автоматически

### 5.2 Проверка канала

```bash
# Посмотрите список каналов
python scripts/account_manager.py db list
```

**Ожидаемый вывод:**
```
📺 Каналы в базе данных:
   Всего: 1
   Включенных: 1
   Авторизованных: 1
   Действительных токенов: 1

   ✅ 🔑 🟢 Мой Первый Канал
```

### 5.3 Тестовая публикация

```bash
# Подготовьте тестовое видео (9:16, 15-60 секунд)
# Опубликуйте на YouTube
python app/main.py post \
  --content data/content/videos/test.mp4 \
  --caption "Тест! #shorts" \
  --platforms youtube
```

---

## 📊 Шаг 6: Добавление дополнительных каналов

### Способ 1: Через CLI (рекомендуется)

```bash
# Добавить второй канал
python scripts/account_manager.py add-channel "Второй Канал" "@channel2" --auto-auth

# Добавить третий канал
python scripts/account_manager.py add-channel "Третий Канал" "@channel3" --auto-auth
```

### Способ 2: Через youtube_manager

```bash
# Если нужны разные OAuth credentials для каждого канала
python run_youtube_manager.py add "Канал с отдельным OAuth" \
  --channel-id "@special" \
  --client-id "другой_client_id" \
  --client-secret "другой_secret"
```

---

## 🎉 Готово!

Ваша YouTube автоматизация настроена! 

### Что дальше?

1. 📖 Изучите [CLI Guide](02-CLI-GUIDE.md) - все команды и примеры
2. 🏗️ Изучите [Architecture](03-ARCHITECTURE.md) - как устроена система
3. 🔧 При проблемах: [Troubleshooting](04-TROUBLESHOOTING.md)

### Полезные команды

```bash
# Список каналов
python scripts/account_manager.py db list

# Авторизовать канал
python scripts/account_manager.py authorize --platform youtube --account "Канал"

# Проверить токены
python run_youtube_manager.py check-tokens

# Опубликовать видео
python app/main.py post --content video.mp4 --caption "Текст" --platforms youtube
```

---

## 📞 Поддержка

При возникновении проблем:

- 📖 [Troubleshooting Guide](04-TROUBLESHOOTING.md)
- 📝 Проверьте логи: `tail -f logs/auto_posting.log`
- 🔍 Проверьте статус: `python scripts/account_manager.py db list`

---

**Следующий шаг:** [CLI Guide →](02-CLI-GUIDE.md)

