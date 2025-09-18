# Настройка множественных аккаунтов

Этот документ описывает, как настроить и использовать множественные аккаунты для каждой социальной сети в системе автопостинга.

## Обзор системы

Система поддерживает:
- ✅ Множественные аккаунты для каждой платформы
- ✅ Автоматическое управление токенами OAuth
- ✅ Автоматическое обновление истекших токенов
- ✅ Валидацию всех аккаунтов
- ✅ Удобную CLI утилиту для управления

## Поддерживаемые платформы

### 1. Instagram (Instagram Graph API)
- **Тип авторизации**: OAuth 2.0 через Facebook Developer
- **Необходимые данные**:
  - `app_id` - ID приложения Facebook/Meta
  - `app_secret` - Секретный ключ приложения
  - `access_token` - Долгосрочный токен доступа (автоматически)
- **Время жизни токенов**: 60 дней (автоматически обновляется)

### 2. TikTok (TikTok for Developers API)
- **Тип авторизации**: OAuth 2.0
- **Необходимые данные**:
  - `client_key` - Ключ клиента приложения
  - `client_secret` - Секретный ключ клиента
  - `access_token` - Токен доступа (автоматически)
  - `refresh_token` - Токен обновления (автоматически)
- **Время жизни токенов**: 24 часа (автоматически обновляется)

### 3. YouTube (YouTube Data API v3)
- **Тип авторизации**: OAuth 2.0 через Google Cloud Console
- **Необходимые данные**:
  - `client_id` - ID клиента Google API
  - `client_secret` - Секретный ключ клиента
  - `credentials_file` - Файл учетных данных OAuth (опционально)
  - `access_token` - Токен доступа (автоматически)
  - `refresh_token` - Токен обновления (автоматически)
- **Время жизни токенов**: 1 час (автоматически обновляется)

## Настройка приложений

### Instagram
1. Перейдите на [Facebook Developer Console](https://developers.facebook.com/)
2. Создайте новое приложение
3. Добавьте продукт "Instagram Basic Display" или "Instagram Graph API"
4. Настройте права доступа: `instagram_basic`, `instagram_content_publish`, `pages_show_list`
5. Добавьте redirect URI: `http://localhost:8080/callback`
6. Получите `app_id` и `app_secret`

### TikTok
1. Перейдите на [TikTok for Developers](https://developers.tiktok.com/)
2. Создайте новое приложение
3. Настройте права доступа: `user.info.basic`, `video.upload`, `video.publish`
4. Добавьте redirect URI: `http://localhost:8080/callback`
5. Получите `client_key` и `client_secret`

### YouTube
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите YouTube Data API v3
4. Создайте OAuth 2.0 учетные данные
5. Добавьте redirect URI: `http://localhost:8080/callback`
6. Скачайте файл учетных данных или получите `client_id` и `client_secret`

## Конфигурация аккаунтов

### 1. Обновите config.yaml

```yaml
accounts:
  instagram:
    - name: "main_account"
      username: "your_main_username"
      app_id: "your_facebook_app_id"
      app_secret: "your_facebook_app_secret"
      enabled: true
    - name: "backup_account"
      username: "your_backup_username"
      app_id: "your_facebook_app_id_2"
      app_secret: "your_facebook_app_secret_2"
      enabled: true
      
  tiktok:
    - name: "main_account"
      username: "your_main_username"
      client_key: "your_tiktok_client_key"
      client_secret: "your_tiktok_client_secret"
      enabled: true
    - name: "backup_account"
      username: "your_backup_username"
      client_key: "your_tiktok_client_key_2"
      client_secret: "your_tiktok_client_secret_2"
      enabled: true
      
  youtube:
    - name: "main_channel"
      channel_id: "your_channel_id"
      client_id: "your_google_client_id"
      client_secret: "your_google_client_secret"
      credentials_file: "credentials.json"  # опционально
      enabled: true
    - name: "backup_channel"
      channel_id: "your_channel_id_2"
      client_id: "your_google_client_id_2"
      client_secret: "your_google_client_secret_2"
      enabled: true
```

### 2. Включите нужные платформы

```yaml
platforms:
  instagram:
    enabled: true  # включить Instagram
  tiktok:
    enabled: true  # включить TikTok
  youtube:
    enabled: true  # включить YouTube
```

## Авторизация аккаунтов

### Автоматическая авторизация всех аккаунтов

```bash
# Авторизовать все аккаунты всех платформ
python account_manager.py authorize --all

# Авторизовать все аккаунты конкретной платформы
python account_manager.py authorize --platform instagram --all
```

### Авторизация конкретного аккаунта

```bash
# Авторизовать конкретный аккаунт
python account_manager.py authorize --platform instagram --account main_account

# Авторизовать без автоматического открытия браузера
python account_manager.py authorize --platform instagram --account main_account --no-browser
```

### Ручная авторизация

```bash
# Получить URL для ручной авторизации
python account_manager.py auth-url instagram main_account

# Добавить токен вручную
python account_manager.py add-token instagram main_account "your_access_token" --refresh-token "your_refresh_token" --expires-in 3600
```

## Управление токенами

### Проверка статуса

```bash
# Проверить статус всех аккаунтов
python account_manager.py status

# Проверить статус конкретной платформы
python account_manager.py status --platform instagram

# Вывод в JSON формате
python account_manager.py status --json
```

### Обновление токенов

```bash
# Обновить все токены
python account_manager.py refresh

# Обновить токены конкретной платформы
python account_manager.py refresh --platform youtube

# Обновить токен конкретного аккаунта
python account_manager.py refresh --platform instagram --account main_account
```

### Валидация аккаунтов

```bash
# Валидировать все аккаунты
python account_manager.py validate

# Валидировать аккаунты конкретной платформы
python account_manager.py validate --platform tiktok

# Вывод в JSON формате
python account_manager.py validate --json
```

### Управление токенами

```bash
# Получить информацию о токене
python account_manager.py token-info instagram main_account

# Удалить токен
python account_manager.py remove-token instagram main_account
```

## Использование в коде

### Постинг на все аккаунты

```python
from src.auto_poster import SocialMediaAutoPoster

auto_poster = SocialMediaAutoPoster()

# Опубликовать на все включенные аккаунты всех платформ
result = auto_poster.post_immediately(
    content_path="./content/videos/my_video.mp4",
    platforms=["instagram", "tiktok", "youtube"],
    caption="Мой пост #hashtag"
)

print(f"Успешных постов: {result['successful_posts']}")
print(f"Неудачных постов: {result['failed_posts']}")
```

### Постинг на конкретные аккаунты

```python
# Опубликовать только на конкретные аккаунты
result = auto_poster.post_immediately(
    content_path="./content/videos/my_video.mp4",
    platforms=["instagram", "youtube"],
    caption="Мой пост #hashtag",
    accounts=["main_account", "backup_account"]  # только эти аккаунты
)
```

### Планирование постов

```python
from datetime import datetime, timedelta

# Запланировать пост на определенное время
scheduled_ids = auto_poster.schedule_post(
    content_path="./content/videos/my_video.mp4",
    platforms=["instagram", "tiktok"],
    caption="Запланированный пост",
    scheduled_time=datetime.now() + timedelta(hours=2),
    accounts=["main_account"]  # только основные аккаунты
)

print(f"Запланировано постов: {len(scheduled_ids)}")
```

### Проверка статуса системы

```python
# Получить подробный статус системы
status = auto_poster.get_system_status()

print("Статус API клиентов:", status['api_clients'])
print("Статус токенов:", status['token_status'])
print("Статус аккаунтов:", status['account_status'])
```

## Автоматическое обслуживание

### Автоматическое обновление токенов

Система автоматически:
- ✅ Проверяет срок действия токенов перед каждым постом
- ✅ Обновляет истекающие токены (за 5 минут до истечения)
- ✅ Логирует все операции с токенами
- ✅ Отправляет уведомления об ошибках авторизации

### Мониторинг

```python
# Настроить автоматическую проверку токенов каждый час
import schedule
import time

def check_tokens():
    auto_poster = SocialMediaAutoPoster()
    results = auto_poster.refresh_account_tokens()
    
    for account, success in results.items():
        if not success:
            print(f"⚠️ Не удалось обновить токен для {account}")

schedule.every().hour.do(check_tokens)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Устранение неполадок

### Распространенные ошибки

#### 1. "Нет действительного токена"
```bash
# Проверить статус токена
python account_manager.py token-info instagram main_account

# Попробовать обновить токен
python account_manager.py refresh --platform instagram --account main_account

# Если не помогает, авторизоваться заново
python account_manager.py authorize --platform instagram --account main_account
```

#### 2. "API валидация не прошла"
- Проверьте правильность app_id/client_id/client_secret
- Убедитесь, что приложение имеет необходимые права доступа
- Проверьте, что redirect URI настроен правильно

#### 3. "Превышено время ожидания авторизации"
```bash
# Получить URL для ручной авторизации
python account_manager.py auth-url instagram main_account
# Откройте URL в браузере и скопируйте код авторизации
```

#### 4. "Аккаунт отключен в конфигурации"
```yaml
# В config.yaml установите enabled: true
accounts:
  instagram:
    - name: "main_account"
      enabled: true  # убедитесь, что это true
```

### Логи и отладка

```bash
# Проверить логи
tail -f logs/auto_posting.log

# Включить подробное логирование
# В config.yaml:
logging:
  level: "DEBUG"  # вместо INFO
```

### Резервное копирование токенов

```bash
# Токены сохраняются в файле tokens.json
cp tokens.json tokens_backup.json

# Восстановление из резервной копии
cp tokens_backup.json tokens.json
```

## Безопасность

### Рекомендации по безопасности

1. **Не коммитьте токены в git**:
   ```bash
   echo "tokens.json" >> .gitignore
   echo "*.json" >> .gitignore  # если используете файлы учетных данных
   ```

2. **Используйте переменные окружения для чувствительных данных**:
   ```yaml
   # В config.yaml можно использовать переменные окружения
   accounts:
     instagram:
       - name: "main_account"
         app_id: "${INSTAGRAM_APP_ID}"
         app_secret: "${INSTAGRAM_APP_SECRET}"
   ```

3. **Регулярно обновляйте токены**:
   ```bash
   # Настройте cron задачу для автоматического обновления
   0 */6 * * * cd /path/to/content-fabric && python account_manager.py refresh
   ```

4. **Мониторьте доступ к аккаунтам**:
   - Регулярно проверяйте активные сессии в настройках аккаунтов
   - Отзывайте доступ для неиспользуемых приложений
   - Используйте разные приложения для разных аккаунтов

### Ограничения API

#### Instagram
- 200 вызовов API в час на приложение
- Максимум 25 постов в день на аккаунт
- Видео должно быть в формате MP4, длительностью 15-90 секунд

#### TikTok
- 100 вызовов API в день на приложение
- Максимум 5 видео в день на аккаунт
- Видео должно быть в формате MP4, размером до 500MB

#### YouTube
- 10,000 квотных единиц в день на проект
- Загрузка видео стоит 1,600 единиц (~6 видео в день)
- Видео должно быть до 128GB или 12 часов

## Заключение

Система множественных аккаунтов обеспечивает:
- 🚀 Масштабируемость - легко добавлять новые аккаунты
- 🔐 Безопасность - автоматическое управление токенами
- 📊 Мониторинг - полная видимость состояния всех аккаунтов
- 🛠️ Удобство - простые CLI команды для управления

Для получения дополнительной помощи обращайтесь к документации API каждой платформы или создавайте issue в репозитории проекта.
