# 🚀 Миграция на продакшн БД

Краткое руководство по выполнению миграции Google Cloud Console на продакшн базу данных.

## Быстрый старт

Если все данные для подключения к продакшн БД находятся в переменных окружения:

```bash
# Убедитесь, что переменные окружения установлены
export MYSQL_HOST=your_prod_host
export MYSQL_PORT=3306
export MYSQL_DATABASE=content_fabric
export MYSQL_USER=your_prod_user
export MYSQL_PASSWORD=your_prod_password

# Запустите миграцию
python3 core/database/migrations/scripts/run_migration_google_consoles.py
```

## Использование .env файла

Если переменные в `.env` файле:

```bash
# .env файл уже загружается автоматически через dotenv
python3 core/database/migrations/scripts/run_migration_google_consoles.py
```

## Проверка подключения

Перед миграцией проверьте подключение:

```bash
python3 core/database/migrations/scripts/check_google_consoles.py
```

Этот скрипт покажет:
- К какой БД подключение (хост, порт, база)
- Существует ли таблица `google_consoles`
- Существует ли колонка `console_id` в `youtube_channels`

## Приоритет загрузки конфигурации

Миграция использует следующий порядок загрузки конфигурации:

1. **Переменные окружения** (MYSQL_HOST, MYSQL_PORT, и т.д.) - для продакшн
2. **Конфиг файл** (`config/mysql_config.yaml`) - для локальной разработки
3. **Параметр --config** - для указания конкретного файла

## Примеры использования

### Продакшн (env переменные)
```bash
export MYSQL_HOST=prod.example.com
export MYSQL_PORT=3306
export MYSQL_DATABASE=content_fabric
export MYSQL_USER=prod_user
export MYSQL_PASSWORD=prod_password
python3 core/database/migrations/scripts/run_migration_google_consoles.py
```

### Локальная разработка (конфиг файл)
```bash
# Использует config/mysql_config.yaml
python3 core/database/migrations/scripts/run_migration_google_consoles.py
```

### Кастомный конфиг файл
```bash
python3 core/database/migrations/scripts/run_migration_google_consoles.py \
  --config config/mysql_config_prod.yaml
```

## После миграции

После успешной миграции:

1. Проверьте статус:
   ```bash
   python3 core/database/migrations/scripts/check_google_consoles.py
   ```

2. Добавьте Google Cloud Console:
   ```bash
   python3 scripts/account_manager.py console add "Console 1" \
     "client-id" "client-secret"
   ```

3. Назначьте консоль каналам:
   ```bash
   python3 scripts/account_manager.py set-console "Channel Name" "Console 1"
   ```

## Troubleshooting

### Ошибка подключения

Если видите ошибку подключения, проверьте:

1. Правильность переменных окружения:
   ```bash
   echo $MYSQL_HOST
   echo $MYSQL_USER
   ```

2. Доступность БД:
   ```bash
   mysql -h $MYSQL_HOST -u $MYSQL_USER -p$MYSQL_PASSWORD $MYSQL_DATABASE
   ```

3. Загружены ли переменные:
   ```bash
   # Если используете .env, убедитесь что он загружается
   source .env
   # или
   export $(cat .env | xargs)
   ```

### Таблица уже существует

Если таблица уже существует, миграция безопасна для повторного запуска - она просто пропустит создание.

---

**Последнее обновление:** 2025-01-XX

