# 🔧 Подробное руководство по настройке API платформ

## 📋 Содержание
1. [Instagram (Meta) API](#instagram-meta-api)
2. [TikTok for Developers](#tiktok-for-developers)
3. [YouTube Data API v3](#youtube-data-api-v3)
4. [Telegram Bot для уведомлений](#telegram-bot-для-уведомлений)
5. [Email SMTP для уведомлений](#email-smtp-для-уведомлений)
6. [Тестирование настроек](#тестирование-настроек)

---

## 📱 Instagram (Meta) API

### Обзор
Instagram использует Facebook Graph API для программного доступа. Для автопостинга нужен Instagram Basic Display API + Instagram Graph API.

### Шаг 1: Создание Facebook приложения

1. **Перейдите на Facebook Developers**
   - Откройте [https://developers.facebook.com/](https://developers.facebook.com/)
   - Войдите в свой Facebook аккаунт

2. **Создайте новое приложение**
   ```
   My Apps → Create App → Consumer → Continue
   ```
   - **Display Name**: "Social Media Auto Poster"
   - **App Contact Email**: ваш email
   - **Purpose**: Автоматизация постинга

3. **Получите App ID и App Secret**
   ```
   Settings → Basic
   ```
   - **App ID**: скопируйте значение
   - **App Secret**: нажмите "Show" и скопируйте

### Шаг 2: Настройка Instagram Basic Display

1. **Добавьте продукт**
   ```
   Products → Instagram Basic Display → Set Up
   ```

2. **Настройте OAuth Redirect URIs**
   ```
   Instagram Basic Display → Basic Display → Settings
   ```
   - **Valid OAuth Redirect URIs**: `https://localhost:8000/auth/callback`
   - **Deauthorize Callback URL**: `https://localhost:8000/auth/deauthorize`

3. **Создайте Instagram Test User**
   ```
   Roles → Roles → Instagram Testers → Add Instagram Testers
   ```
   - Введите ваш Instagram username
   - Перейдите в Instagram → Settings → Apps and Websites → Tester Invites
   - Примите приглашение

### Шаг 3: Получение Access Token

1. **Сгенерируйте Authorization URL**
   ```
   https://api.instagram.com/oauth/authorize
     ?client_id={app-id}
     &redirect_uri={redirect-uri}
     &scope=user_profile,user_media
     &response_type=code
   ```

2. **Замените параметры**
   ```
   https://api.instagram.com/oauth/authorize
     ?client_id=YOUR_APP_ID
     &redirect_uri=https://localhost:8000/auth/callback
     &scope=user_profile,user_media
     &response_type=code
   ```

3. **Получите Authorization Code**
   - Откройте URL в браузере
   - Авторизуйтесь
   - Скопируйте `code` из redirect URL

4. **Обменяйте код на токен**
   ```bash
   curl -X POST \
     https://api.instagram.com/oauth/access_token \
     -F client_id=YOUR_APP_ID \
     -F client_secret=YOUR_APP_SECRET \
     -F grant_type=authorization_code \
     -F redirect_uri=https://localhost:8000/auth/callback \
     -F code=AUTHORIZATION_CODE
   ```

### Шаг 4: Конфигурация в проекте

**config.yaml:**
```yaml
accounts:
  instagram:
    - name: "my_instagram"
      username: "your_instagram_username"
      access_token: "IGQVJ..."  # Полученный токен
      app_id: "123456789"
      app_secret: "abc123def456"
      enabled: true
```

**.env:**
```bash
INSTAGRAM_APP_ID=123456789
INSTAGRAM_APP_SECRET=abc123def456
INSTAGRAM_ACCESS_TOKEN=IGQVJ...
```

### Ограничения и требования

**Rate Limits:**
- 200 запросов в час на приложение
- 25 медиа объектов в день на пользователя

**Требования к контенту:**
- **Формат**: MP4, MOV
- **Соотношение сторон**: 9:16 (обязательно для Reels)
- **Длительность**: 3-90 секунд
- **Размер файла**: до 100MB
- **Разрешение**: минимум 720p, рекомендуется 1080x1920

---

## 🎵 TikTok for Developers

### Обзор
TikTok предоставляет API для бизнес-аккаунтов через TikTok for Developers platform.

### Шаг 1: Подача заявки на доступ

1. **Перейдите на TikTok for Developers**
   - Откройте [https://developers.tiktok.com/](https://developers.tiktok.com/)
   - Нажмите "Get Started"

2. **Заполните заявку**
   - **Company/Organization**: ваша компания или "Individual"
   - **Use Case**: "Content Management and Publishing"
   - **App Description**: описание вашего проекта автопостинга
   - **Expected Monthly Active Users**: примерное количество

3. **Дождитесь одобрения**
   - Процесс может занять 1-7 дней
   - Проверяйте email на уведомления

### Шаг 2: Создание приложения

1. **Создайте новое приложение**
   ```
   Manage Apps → Create an App
   ```
   - **App Name**: "Social Media Auto Poster"
   - **Category**: "Productivity & Utilities"
   - **Description**: описание функций

2. **Настройте OAuth**
   ```
   App Settings → Login Kit → Configure
   ```
   - **Redirect URI**: `https://localhost:8000/auth/tiktok/callback`
   - **Scopes**: `user.info.basic`, `video.upload`

3. **Получите Client Key и Client Secret**
   ```
   App Settings → Basic Information
   ```

### Шаг 3: OAuth авторизация

1. **Создайте Authorization URL**
   ```
   https://www.tiktok.com/auth/authorize/
     ?client_key={client_key}
     &scope=user.info.basic,video.upload
     &response_type=code
     &redirect_uri={redirect_uri}
     &state={state}
   ```

2. **Получите Authorization Code**
   - Откройте URL в браузере
   - Войдите в TikTok аккаунт
   - Разрешите доступ
   - Скопируйте код из redirect URL

3. **Обменяйте код на токен**
   ```bash
   curl -X POST \
     https://open-api.tiktok.com/oauth/access_token/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "client_key=YOUR_CLIENT_KEY" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "code=AUTHORIZATION_CODE" \
     -d "grant_type=authorization_code"
   ```

### Шаг 4: Конфигурация в проекте

**config.yaml:**
```yaml
accounts:
  tiktok:
    - name: "my_tiktok"
      username: "your_tiktok_username"
      access_token: "act.example123"
      client_key: "aw123456789"
      client_secret: "abc123def456"
      enabled: true
```

**.env:**
```bash
TIKTOK_CLIENT_KEY=aw123456789
TIKTOK_CLIENT_SECRET=abc123def456
TIKTOK_ACCESS_TOKEN=act.example123
```

### Ограничения и требования

**Rate Limits:**
- Зависят от endpoint
- Video Upload: 10 видео в час
- User Info: 100 запросов в час

**Требования к контенту:**
- **Формат**: MP4, MOV, WEBM
- **Соотношение сторон**: 9:16 (рекомендуется)
- **Длительность**: 3 секунды - 10 минут
- **Размер файла**: до 500MB
- **Разрешение**: минимум 540x960, рекомендуется 1080x1920

---

## 📺 YouTube Data API v3

### Обзор
YouTube использует Google APIs для программного доступа к платформе.

### Шаг 1: Настройка Google Cloud Console

1. **Создайте проект**
   - Откройте [Google Cloud Console](https://console.cloud.google.com/)
   - Нажмите "Select a project" → "New Project"
   - **Project Name**: "Social Media Auto Poster"
   - **Organization**: оставьте пустым или выберите

2. **Включите YouTube Data API v3**
   ```
   APIs & Services → Library → YouTube Data API v3 → Enable
   ```

3. **Создайте OAuth 2.0 Credentials**
   ```
   APIs & Services → Credentials → Create Credentials → OAuth client ID
   ```
   - **Application Type**: "Desktop application"
   - **Name**: "Auto Poster Client"
   - Скачайте JSON файл как `credentials.json`

### Шаг 2: Настройка OAuth Consent Screen

1. **Настройте Consent Screen**
   ```
   APIs & Services → OAuth consent screen
   ```
   - **User Type**: External (для личного использования)
   - **App Name**: "Social Media Auto Poster"
   - **User support email**: ваш email
   - **Developer contact**: ваш email

2. **Добавьте Scopes**
   ```
   Scopes → Add or Remove Scopes
   ```
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube`

3. **Добавьте Test Users**
   ```
   Test users → Add Users
   ```
   - Добавьте ваш Google аккаунт

### Шаг 3: Первая авторизация

1. **Поместите credentials.json в проект**
   ```bash
   cp ~/Downloads/credentials.json /path/to/content-fabric/
   ```

2. **Запустите авторизацию**
   ```python
   python3 -c "
   from src.api_clients.youtube_client import YouTubeClient
   client = YouTubeClient('client_id', 'client_secret', 'credentials.json')
   print('YouTube client initialized')
   "
   ```

3. **Пройдите OAuth flow**
   - Откроется браузер
   - Войдите в Google аккаунт
   - Разрешите доступ
   - Токены сохранятся в `youtube_token.json`

### Шаг 4: Конфигурация в проекте

**config.yaml:**
```yaml
accounts:
  youtube:
    - name: "my_channel"
      channel_id: "UC..."  # Получится автоматически
      access_token: "ya29..."  # Из youtube_token.json
      client_id: "123-abc.apps.googleusercontent.com"
      client_secret: "GOCSPX-..."
      credentials_file: "credentials.json"
      enabled: true
```

**.env:**
```bash
YOUTUBE_CLIENT_ID=123-abc.apps.googleusercontent.com
YOUTUBE_CLIENT_SECRET=GOCSPX-...
YOUTUBE_REFRESH_TOKEN=1//04...
```

### Ограничения и требования

**Quota Limits:**
- 10,000 единиц квоты в день (бесплатно)
- Video upload = 1,600 единиц
- Максимум ~6 загрузок в день

**Требования к контенту:**
- **Формат**: MP4, MOV, AVI, WMV, FLV, WebM
- **Соотношение сторон**: 9:16 для Shorts
- **Длительность**: до 60 секунд для Shorts
- **Размер файла**: до 256MB (или 15 минут)
- **Разрешение**: любое, рекомендуется 1080x1920

---

## 🤖 Telegram Bot для уведомлений

### Шаг 1: Создание бота

1. **Найдите BotFather**
   - Откройте Telegram
   - Найдите @BotFather
   - Начните диалог

2. **Создайте нового бота**
   ```
   /newbot
   ```
   - **Bot Name**: "Social Media Auto Poster Bot"
   - **Username**: "your_autoposting_bot" (должен заканчиваться на "bot")

3. **Получите Bot Token**
   - BotFather отправит токен вида: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`

### Шаг 2: Получение Chat ID

1. **Отправьте сообщение боту**
   - Найдите вашего бота по username
   - Отправьте любое сообщение (например, "/start")

2. **Получите Chat ID через API**
   ```bash
   curl https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   ```
   - Найдите в ответе `"chat":{"id":123456789}`
   - Скопируйте это число

### Шаг 3: Конфигурация

**.env:**
```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_CHAT_ID=123456789
```

**config.yaml:**
```yaml
notifications:
  telegram:
    enabled: true
    send_success: true
    send_failure: true
```

### Тестирование
```bash
python3 main.py test-notifications
```

---

## 📧 Email SMTP для уведомлений

### Gmail SMTP

1. **Включите 2FA в Google аккаунте**
   - Google Account → Security → 2-Step Verification

2. **Создайте App Password**
   - Google Account → Security → App passwords
   - **App**: "Mail"
   - **Device**: "Other" → "Social Media Auto Poster"
   - Скопируйте сгенерированный пароль

3. **Конфигурация**

**.env:**
```bash
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=generated_app_password
```

### Другие провайдеры

**Outlook/Hotmail:**
```bash
EMAIL_SMTP_SERVER=smtp-mail.outlook.com
EMAIL_SMTP_PORT=587
```

**Yahoo:**
```bash
EMAIL_SMTP_SERVER=smtp.mail.yahoo.com
EMAIL_SMTP_PORT=587
```

**Yandex:**
```bash
EMAIL_SMTP_SERVER=smtp.yandex.ru
EMAIL_SMTP_PORT=587
```

---

## 🧪 Тестирование настроек

### Пошаговая проверка

1. **Проверьте конфигурацию**
   ```bash
   python3 main.py status
   ```

2. **Проверьте аккаунты**
   ```bash
   python3 main.py validate-accounts
   ```

3. **Проверьте уведомления**
   ```bash
   python3 main.py test-notifications
   ```

4. **Тестовый пост (с отключенными платформами)**
   ```bash
   # Убедитесь что enabled: false в config.yaml
   python3 main.py post \
     --content content/videos/test.mp4 \
     --caption "Test post" \
     --platforms "instagram"
   ```

### Диагностика проблем

**401 Unauthorized:**
- Проверьте токены доступа
- Убедитесь что токены не истекли
- Для YouTube удалите `youtube_token.json` и пройдите OAuth заново

**403 Forbidden:**
- Проверьте права доступа (scopes)
- Убедитесь что аккаунт подтвержден в API платформы

**429 Rate Limited:**
- Система автоматически обрабатывает лимиты
- Проверьте логи для деталей

**500 Server Error:**
- Проблема на стороне API платформы
- Повторите запрос позже

### Логи для диагностики

```bash
# Просмотр всех логов
tail -f logs/auto_posting.log

# Только ошибки
grep "ERROR" logs/auto_posting.log

# API вызовы
grep "API" logs/auto_posting.log
```

---

## 🔒 Безопасность

### Рекомендации по безопасности

1. **Никогда не публикуйте токены**
   - Используйте `.env` файлы
   - Добавьте `.env` в `.gitignore`

2. **Регулярно обновляйте токены**
   - Instagram: токены действуют 60 дней
   - TikTok: токены действуют 1 год
   - YouTube: refresh токены не истекают

3. **Используйте минимальные права**
   - Запрашивайте только необходимые scopes
   - Регулярно проверяйте разрешения

4. **Мониторинг активности**
   - Проверяйте логи на подозрительную активность
   - Настройте уведомления об ошибках

### Backup токенов

```bash
# Создайте backup важных файлов
cp .env .env.backup
cp youtube_token.json youtube_token.json.backup
cp credentials.json credentials.json.backup
```

Это руководство поможет вам настроить все API платформы для работы с системой автопостинга.
