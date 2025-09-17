**# Техническая документация - Social Media Auto-Poster**

## 📋 Содержание
1. [Архитектура системы](#архитектура-системы)
2. [Структура проекта](#структура-проекта)
3. [Компоненты системы](#компоненты-системы)
4. [Настройка API платформ](#настройка-api-платформ)
5. [Конфигурационные файлы](#конфигурационные-файлы)
6. [Установка и запуск](#установка-и-запуск)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ Архитектура систем

### Общая схема
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CLI Interface │────│  Auto Poster     │────│  API Clients    │
│   (main.py)     │    │  (координатор)   │    │  (платформы)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
        │   Scheduler  │ │ Notifications│ │   Logger   │
        │ (планировщик)│ │ (уведомления)│ │ (логирование)│
        └──────────────┘ └─────────────┘ └────────────┘
```

### Принцип работы
1. **CLI** принимает команды пользователя
2. **Auto Poster** координирует все компоненты
3. **API Clients** взаимодействуют с платформами
4. **Scheduler** управляет расписанием постов
5. **Notifications** отправляют уведомления
6. **Logger** ведет подробные логи

---

## 📁 Структура проекта

```
content-fabric/
├── 📄 main.py                    # Основной CLI интерфейс
├── 📄 setup.py                   # Скрипт установки
├── 📄 example_usage.py           # Примеры использования
├── 📄 requirements.txt           # Python зависимости
├── 📄 config.yaml               # Основная конфигурация
├── 📄 config.env.example        # Шаблон переменных окружения
├── 📄 README.md                 # Пользовательская документация
├── 📄 TECHNICAL_DOCS.md         # Техническая документация
├── 📄 .gitignore               # Git исключения
│
├── 📂 src/                      # Исходный код
│   ├── 📄 __init__.py
│   ├── 📄 auto_poster.py        # Главный координатор
│   ├── 📄 logger.py             # Система логирования
│   ├── 📄 scheduler.py          # Планировщик постов
│   ├── 📄 notifications.py      # Система уведомлений
│   ├── 📄 content_processor.py  # Обработка контента (отключен)
│   └── 📂 api_clients/          # API клиенты платформ
│       ├── 📄 __init__.py
│       ├── 📄 base_client.py    # Базовый API клиент
│       ├── 📄 instagram_client.py # Instagram API
│       ├── 📄 tiktok_client.py    # TikTok API
│       └── 📄 youtube_client.py   # YouTube API
│
├── 📂 content/                  # Контент для постинга
│   ├── 📂 videos/              # Исходные видео
│   ├── 📂 descriptions/        # Описания постов
│   ├── 📂 thumbnails/          # Превью изображения
│   └── 📂 processed/           # Обработанные файлы
│
└── 📂 logs/                    # Файлы логов
    └── 📄 auto_posting.log     # Основной лог файл
```

---

## 🔧 Компоненты системы

### 1. **main.py** - CLI Интерфейс
**Назначение**: Командная строка для управления системой

**Основные команды**:
```bash
python3 main.py post           # Немедленная публикация
python3 main.py schedule       # Планирование постов
python3 main.py start-scheduler # Запуск планировщика
python3 main.py status         # Статус системы
python3 main.py validate-accounts # Проверка аккаунтов
```

### 2. **auto_poster.py** - Главный координатор
**Назначение**: Координирует все компоненты системы

**Основные методы**:
- `post_immediately()` - Немедленная публикация
- `schedule_post()` - Планирование поста
- `validate_accounts()` - Проверка аккаунтов
- `get_system_status()` - Статус системы

### 3. **API Clients** - Клиенты платформ
**Назначение**: Взаимодействие с API социальных сетей

#### base_client.py
- Базовый класс для всех API клиентов
- Обработка rate limits
- Retry логика
- Общие HTTP методы

#### instagram_client.py
- Instagram Graph API
- Публикация Reels
- Управление медиа контейнерами

#### tiktok_client.py
- TikTok for Developers API
- Загрузка видео
- Публикация контента

#### youtube_client.py
- YouTube Data API v3
- Публикация Shorts
- OAuth аутентификация

### 4. **scheduler.py** - Планировщик
**Назначение**: Управление расписанием публикаций

**Функции**:
- Планирование на конкретное время
- Случайное время в диапазонах
- Retry логика для неудачных постов
- Сохранение состояния в JSON

### 5. **notifications.py** - Уведомления
**Назначение**: Отправка уведомлений о результатах

**Каналы**:
- Telegram Bot API
- Email (SMTP)
- Уведомления об успехе/неудаче

### 6. **logger.py** - Логирование
**Назначение**: Детальное логирование всех операций

**Особенности**:
- Цветной вывод в консоль
- Ротация лог файлов
- Разные уровни логирования
- Специальные методы для постинга

---

## 🔑 Настройка API платформ

### 📱 Instagram (Meta)

#### Шаг 1: Создание приложения
1. Перейдите на [Facebook Developers](https://developers.facebook.com/)
2. Создайте новое приложение
3. Добавьте продукт "Instagram Basic Display"

#### Шаг 2: Настройка приложения
```yaml
# В config.yaml
accounts:
  instagram:
    - name: "my_account"
      username: "your_username"
      access_token: "YOUR_ACCESS_TOKEN"
      app_id: "YOUR_APP_ID"
      app_secret: "YOUR_APP_SECRET"
      enabled: true
```

#### Шаг 3: Получение токенов
1. **App ID** и **App Secret** - из настроек приложения
2. **Access Token** - через Instagram Basic Display API
3. **User ID** - получается автоматически

#### Требования к контенту:
- **Формат**: MP4, MOV
- **Соотношение сторон**: 9:16 (вертикальное)
- **Длительность**: 15-90 секунд
- **Размер**: до 100MB
- **Разрешение**: рекомендуется 1080x1920

#### Rate Limits:
- ~200 запросов в час на приложение
- Ограничения на количество постов в день

---

### 🎵 TikTok

#### Шаг 1: Регистрация разработчика
1. Подайте заявку на [TikTok for Developers](https://developers.tiktok.com/)
2. Дождитесь одобрения (может занять несколько дней)
3. Создайте приложение

#### Шаг 2: Настройка приложения
```yaml
# В config.yaml
accounts:
  tiktok:
    - name: "my_tiktok"
      username: "your_username"
      access_token: "YOUR_ACCESS_TOKEN"
      client_key: "YOUR_CLIENT_KEY"
      client_secret: "YOUR_CLIENT_SECRET"
      enabled: true
```

#### Шаг 3: OAuth процесс
1. **Client Key** и **Client Secret** - из настроек приложения
2. **Access Token** - через OAuth 2.0 flow
3. **Refresh Token** - для обновления токенов

#### Требования к контенту:
- **Формат**: MP4, MOV
- **Соотношение сторон**: 9:16 (вертикальное)
- **Длительность**: 15-180 секунд
- **Размер**: до 500MB
- **Разрешение**: рекомендуется 1080x1920

#### Rate Limits:
- Зависят от endpoint'а
- Обычно 100-300 запросов в час

---

### 📺 YouTube

#### Шаг 1: Google Cloud Console
1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите YouTube Data API v3
3. Создайте OAuth 2.0 credentials

#### Шаг 2: Настройка credentials
```yaml
# В config.yaml
accounts:
  youtube:
    - name: "my_channel"
      channel_id: "YOUR_CHANNEL_ID"
      access_token: "YOUR_ACCESS_TOKEN"
      client_id: "YOUR_CLIENT_ID"
      client_secret: "YOUR_CLIENT_SECRET"
      credentials_file: "credentials.json"
      enabled: true
```

#### Шаг 3: OAuth настройка
1. Скачайте `credentials.json` из Google Cloud Console
2. При первом запуске пройдите OAuth авторизацию
3. Токены сохранятся в `youtube_token.json`

#### Требования к контенту:
- **Формат**: MP4, MOV
- **Соотношение сторон**: 9:16 (вертикальное)
- **Длительность**: до 60 секунд для Shorts
- **Размер**: до 256MB
- **Разрешение**: рекомендуется 1080x1920

#### Quota Limits:
- 10,000 единиц квоты в день
- Загрузка видео = 1,600 единиц
- ~6 загрузок в день на бесплатном тарифе

---

## ⚙️ Конфигурационные файлы

### config.yaml - Основная конфигурация

```yaml
# Настройки платформ
platforms:
  instagram:
    enabled: true/false          # Включить/выключить платформу
    max_duration: 90             # Максимальная длительность (сек)
    min_duration: 15             # Минимальная длительность (сек)
    aspect_ratio: "9:16"         # Соотношение сторон
    file_formats: ["mp4", "mov"] # Поддерживаемые форматы

# Аккаунты
accounts:
  instagram:
    - name: "account_name"       # Уникальное имя аккаунта
      username: "instagram_user" # Username в Instagram
      access_token: "token"      # Access Token
      app_id: "app_id"          # Facebook App ID
      app_secret: "app_secret"   # Facebook App Secret
      enabled: true              # Активен ли аккаунт

# Расписание постинга
schedule:
  specific_times:                # Конкретные времена
    - "09:00"
    - "12:00"
    - "18:00"
  
  random_ranges:                 # Случайные диапазоны
    - start: "08:00"
      end: "10:00"
    - start: "14:00"
      end: "16:00"
  
  posting_days: [0,1,2,3,4,5,6] # Дни недели (0=Понедельник)
  timezone: "UTC"                # Часовой пояс

# Контент настройки
content:
  default_hashtags:              # Хештеги для всех постов
    - "#shorts"
    - "#viral"
  
  platform_hashtags:            # Хештеги для конкретных платформ
    instagram:
      - "#reels"
    tiktok:
      - "#fyp"
    youtube:
      - "#youtubeshorts"

# Уведомления
notifications:
  telegram:
    enabled: true
    send_success: true           # Уведомления об успехе
    send_failure: true           # Уведомления о неудаче
  
  email:
    enabled: true
    send_success: false          # Только неудачи по email
    send_failure: true
  
  recipients:                    # Получатели уведомлений
    - "admin@example.com"

# Логирование
logging:
  level: "INFO"                  # DEBUG, INFO, WARNING, ERROR
  file: "./logs/auto_posting.log"
  max_size: "10MB"
  backup_count: 5

# Retry настройки
retry:
  max_attempts: 3                # Максимум попыток
  delay_seconds: 60              # Задержка между попытками
  backoff_multiplier: 2          # Множитель задержки
```

### .env - Переменные окружения

```bash
# Instagram API
INSTAGRAM_APP_ID=your_app_id
INSTAGRAM_APP_SECRET=your_app_secret
INSTAGRAM_ACCESS_TOKEN=your_access_token

# TikTok API
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret
TIKTOK_ACCESS_TOKEN=your_access_token

# YouTube API
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
YOUTUBE_REFRESH_TOKEN=your_refresh_token

# Telegram уведомления
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email уведомления
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Общие настройки
LOG_LEVEL=INFO
CONTENT_FOLDER=./content
OUTPUT_FOLDER=./output
```

---

## 🚀 Установка и запуск

### Требования к системе
- **Python**: 3.8+
- **ОС**: Windows, macOS, Linux
- **RAM**: минимум 512MB
- **Диск**: 1GB свободного места

### Установка зависимостей

```bash
# Клонирование проекта
git clone <repository-url>
cd content-fabric

# Установка Python зависимостей
pip3 install -r requirements.txt

# Настройка конфигурации
cp config.env.example .env
# Отредактируйте .env и config.yaml
```

### Первый запуск

```bash
# 1. Проверка системы
python3 main.py status

# 2. Проверка аккаунтов
python3 main.py validate-accounts

# 3. Тестовая публикация (с отключенными платформами)
python3 main.py post --content content/videos/test.mp4 --caption "Test post" --platforms "instagram"

# 4. Запуск планировщика
python3 main.py start-scheduler
```

### Структура команд

#### Немедленная публикация
```bash
python3 main.py post \
  --content path/to/video.mp4 \
  --caption "Your caption #hashtag" \
  --platforms "instagram,tiktok,youtube" \
  --accounts "account1,account2" \
  --metadata '{"privacy":"public"}'
```

#### Планирование постов
```bash
# Случайное время
python3 main.py schedule \
  --content path/to/video.mp4 \
  --caption "Scheduled post" \
  --platforms "instagram,tiktok"

# Конкретное время
python3 main.py schedule \
  --content path/to/video.mp4 \
  --caption "Scheduled post" \
  --platforms "instagram" \
  --time "2024-01-15T18:00:00"
```

#### Управление расписанием
```bash
# Список запланированных постов
python3 main.py list-scheduled

# Отмена поста
python3 main.py cancel --post-id "instagram_account1_1705123456"

# Статистика
python3 main.py stats
```

---

## 🔍 Troubleshooting

### Частые проблемы

#### 1. ModuleNotFoundError
```bash
# Проблема: Модуль не найден
# Решение: Установите зависимости
pip3 install -r requirements.txt

# Если не помогает, установите конкретный модуль
pip3 install requests pyyaml python-dotenv
```

#### 2. API Authentication Errors
```bash
# Проблема: 401 Unauthorized
# Решение: Проверьте токены доступа
python3 main.py validate-accounts

# Обновите токены в .env файле
# Для YouTube - удалите youtube_token.json и пройдите OAuth заново
```

#### 3. Content Processing Errors
```bash
# Проблема: Ошибки обработки видео
# В текущей версии обработка отключена
# Убедитесь что ваше видео соответствует требованиям:
# - Формат: MP4
# - Соотношение: 9:16
# - Длительность: 15-60 секунд
```

#### 4. Rate Limit Errors
```bash
# Проблема: 429 Too Many Requests
# Решение: Система автоматически обрабатывает rate limits
# Проверьте логи для деталей:
tail -f logs/auto_posting.log
```

#### 5. Scheduler не запускается
```bash
# Проблема: Планировщик не работает
# Решение: Проверьте конфигурацию
python3 main.py status

# Запустите в debug режиме
LOG_LEVEL=DEBUG python3 main.py start-scheduler
```

### Логи и диагностика

#### Местоположение логов
- **Основные логи**: `logs/auto_posting.log`
- **Ротация**: автоматическая при достижении 10MB
- **Уровни**: DEBUG, INFO, WARNING, ERROR

#### Полезные команды для диагностики
```bash
# Просмотр логов в реальном времени
tail -f logs/auto_posting.log

# Поиск ошибок
grep "ERROR" logs/auto_posting.log

# Статистика постов
grep "Successfully posted" logs/auto_posting.log | wc -l

# Проверка API соединений
python3 -c "
from src.auto_poster import SocialMediaAutoPoster
poster = SocialMediaAutoPoster()
print(poster.get_system_status())
"
```

### Контакты для поддержки

При возникновении проблем:
1. Проверьте логи в `logs/auto_posting.log`
2. Убедитесь в корректности конфигурации
3. Проверьте статус API платформ
4. Создайте issue с подробным описанием проблемы

---

## 📊 Мониторинг и метрики

### Ключевые метрики
- **Успешность постов**: процент успешных публикаций
- **Rate limit hits**: количество превышений лимитов
- **API response time**: время отклика API
- **Queue size**: размер очереди запланированных постов

### Команды мониторинга
```bash
# Общая статистика
python3 main.py stats

# Статус системы
python3 main.py status

# Список запланированных постов
python3 main.py list-scheduled
```

Эта документация покрывает все аспекты системы и поможет вам настроить и использовать Social Media Auto-Poster эффективно.
