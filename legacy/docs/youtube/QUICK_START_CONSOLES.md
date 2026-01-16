# 🚀 Быстрый старт: Добавление консолей и назначение каналам

Краткое руководство по работе с Google Cloud Console проектами.

## Шаг 1: Добавление Google Cloud Console

### Вариант A: Из credentials.json файла

Если у вас есть `credentials.json` файл:

```bash
# Прочитайте project_id и redirect_uris из файла
# Затем добавьте консоль:
python3 scripts/account_manager.py console add "Console 1" \
  "923063452206-78e3f9ea06pv5snaegs2a78i5na5o7hk.apps.googleusercontent.com" \
  "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" \
  --project-id "contentfactory-472516" \
  --redirect-uris "http://localhost" \
  --credentials-file "credentials1.json" \
  --description "Основная консоль для продакшн"
```

### Вариант B: Минимальная информация

Если нужны только обязательные поля:

```bash
python3 scripts/account_manager.py console add "Console 1" \
  "your-client-id.apps.googleusercontent.com" \
  "GOCSPX-your-client-secret"
```

### Вариант C: Несколько консолей

```bash
# Консоль 1
python3 scripts/account_manager.py console add "Main Console" \
  "client-id-1" "secret-1" \
  --project-id "project-1" \
  --description "Основная консоль"

# Консоль 2
python3 scripts/account_manager.py console add "Secondary Console" \
  "client-id-2" "secret-2" \
  --project-id "project-2" \
  --description "Дополнительная консоль"
```

## Шаг 2: Просмотр добавленных консолей

```bash
python3 scripts/account_manager.py console list
```

Вывод:
```
📱 Google Cloud Consoles:
   ✅ Main Console (ID: 1)
      Project ID: contentfactory-472516
      Описание: Основная консоль
      Credentials: credentials1.json
      Redirect URIs: http://localhost
      Создана: 2025-01-XX XX:XX:XX
   
   ✅ Secondary Console (ID: 2)
      Project ID: project-2
      Описание: Дополнительная консоль
      Создана: 2025-01-XX XX:XX:XX
```

## Шаг 3: Назначение консоли каналу

### Для нового канала

```bash
python3 scripts/account_manager.py add-channel "My Channel" "@mychannel" \
  --console "Main Console" \
  --auto-auth
```

### Для существующего канала

```bash
# Установить консоль
python3 scripts/account_manager.py set-console "My Channel" "Main Console"

# Или использовать другую консоль
python3 scripts/account_manager.py set-console "My Channel" "Secondary Console"

# Удалить связь с консолью
python3 scripts/account_manager.py set-console "My Channel" "none"
```

## Шаг 4: Проверка назначений

```bash
# Просмотр всех каналов
python3 scripts/account_manager.py db list
```

Каналы с назначенной консолью будут использовать credentials из этой консоли.

## Пример полного workflow

```bash
# 1. Добавить первую консоль
python3 scripts/account_manager.py console add "Prod Console" \
  "client-id-1" "secret-1" \
  --project-id "prod-project" \
  --description "Продакшн консоль"

# 2. Добавить вторую консоль
python3 scripts/account_manager.py console add "Dev Console" \
  "client-id-2" "secret-2" \
  --project-id "dev-project" \
  --description "Дев консоль"

# 3. Добавить каналы с консолями
python3 scripts/account_manager.py add-channel "Channel 1" "@channel1" \
  --console "Prod Console" \
  --auto-auth

python3 scripts/account_manager.py add-channel "Channel 2" "@channel2" \
  --console "Prod Console" \
  --auto-auth

python3 scripts/account_manager.py add-channel "Test Channel" "@test" \
  --console "Dev Console" \
  --auto-auth

# 4. Назначить консоль существующему каналу
python3 scripts/account_manager.py set-console "Existing Channel" "Prod Console"

# 5. Проверить результат
python3 scripts/account_manager.py console list
python3 scripts/account_manager.py db list
```

## Где взять данные для консоли?

### Из Google Cloud Console:

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Выберите проект
3. Перейдите: **APIs & Services** → **Credentials**
4. Найдите OAuth 2.0 Client ID
5. Скопируйте:
   - **Client ID** (например: `923063452206-...apps.googleusercontent.com`)
   - **Client Secret** (например: `GOCSPX-...`)
   - **Project ID** (вверху страницы, например: `contentfactory-472516`)

### Из credentials.json:

Если у вас есть файл `credentials.json`:

```json
{
  "installed": {
    "client_id": "923063452206-78e3f9ea06pv5snaegs2a78i5na5o7hk.apps.googleusercontent.com",
    "project_id": "contentfactory-472516",
    "client_secret": "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",
    "redirect_uris": ["http://localhost"]
  }
}
```

Используйте:
- `client_id` → первый аргумент
- `client_secret` → второй аргумент
- `project_id` → `--project-id`
- `redirect_uris[0]` → `--redirect-uris`

## Полезные команды

```bash
# Список всех консолей
python3 scripts/account_manager.py console list

# Удалить консоль (связи с каналами будут удалены)
python3 scripts/account_manager.py console remove "Console Name"

# Список всех каналов
python3 scripts/account_manager.py db list

# Проверить статус миграции
python3 core/database/migrations/scripts/check_google_consoles.py
```

## Troubleshooting

### Консоль не найдена

Убедитесь, что консоль существует:
```bash
python3 scripts/account_manager.py console list
```

### Канал не использует консоль

Проверьте назначение:
```bash
python3 scripts/account_manager.py db list
```

Если консоль не назначена, установите:
```bash
python3 scripts/account_manager.py set-console "Channel Name" "Console Name"
```

### Ошибка авторизации после смены консоли

Если вы сменили консоль для канала, может потребоваться повторная авторизация:
```bash
python3 scripts/account_manager.py authorize --platform youtube --account "Channel Name"
```

---

**Последнее обновление:** 2025-01-XX

